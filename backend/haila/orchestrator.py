from __future__ import annotations

import hashlib
import random
import re
from typing import Any

from .contracts import DistratorGerado, NucleoQuestao, RedFlag, ReferenciaRAG
from .domain import ESTADOS_TERMINAIS, Estado
from .repository import HailaRepository
from .structural import avaliar_distratores, avaliar_item, avaliar_nucleo


class HailaOrchestrator:
    """Coordena RAG, LLM, SLM, montagem, red flags e revisão humana."""
    def __init__(self, repository: HailaRepository): self.repo = repository

    def solicitar(self, solicitante_id: str, specification: dict, max_attempts: int = 3,
                  max_distractor_attempts: int = 3) -> dict:
        if min(max_attempts, max_distractor_attempts) < 1: raise ValueError("limites devem ser positivos")
        rid = self.repo.create_request(solicitante_id, specification, max_attempts, max_distractor_attempts)
        return self.repo.get_request(rid)

    def executar(self, request_id: str, rag, stem_generator, distractor_generator, red_flag_analyzer) -> dict:
        """Executa a geração e garante que toda solicitação termine em estado terminal.

        Qualquer exceção não tratada (RAG sem referência, cota do provedor,
        falha ao carregar a SLM etc.) leva a GENERATION_FAILED antes de ser
        propagada. Sem isso, a solicitação ficaria parada num estado
        intermediário e o histórico não explicaria o encerramento.
        """
        try:
            return self._executar(request_id, rag, stem_generator, distractor_generator, red_flag_analyzer)
        except Exception as exc:
            try:
                atual = Estado(self.repo.get_request(request_id)["state"])
                if atual not in ESTADOS_TERMINAIS:
                    self.repo.transition(
                        request_id, None, Estado.GENERATION_FAILED, "HAILA",
                        "execução interrompida por exceção",
                        {"excecao": type(exc).__name__, "mensagem": str(exc)[:500]},
                    )
            except Exception:
                pass
            raise

    def _executar(self, request_id: str, rag, stem_generator, distractor_generator, red_flag_analyzer) -> dict:
        req = self.repo.get_request(request_id)
        referencia: ReferenciaRAG = rag(req["specification"])
        self.repo.save_artifact(request_id, "REFERENCE", referencia.to_dict(), {})
        self.repo.transition(request_id, None, Estado.REFERENCE_RETRIEVED, "HAILA_RAG", "referência recuperada", {"id": referencia.id})
        feedback_nucleo, feedback_distratores = [], []
        nucleo: NucleoQuestao | None = None

        while req["stem_attempts"] < req["max_attempts"]:
            if nucleo is None:
                try:
                    nucleo, prov = stem_generator(req["specification"], referencia, feedback_nucleo)
                except ValueError as exc:
                    self.repo.increment_attempt(request_id, "stem")
                    flag = RedFlag(
                        "formatacao_quebrada", "NUCLEO", "saida_llm",
                        f"núcleo não pôde ser interpretado: {exc}", "NUCLEO"
                    )
                    feedback_nucleo = [flag.to_dict()]
                    self.repo.record_flags(request_id, feedback_nucleo)
                    self.repo.transition(
                        request_id, None, Estado.BLOCKED_BY_RED_FLAGS, "HAILA_RED_FLAGS",
                        "saída inválida da LLM; nova tentativa solicitada",
                        {"red_flags": feedback_nucleo},
                    )
                    req = self.repo.get_request(request_id)
                    continue
                self.repo.increment_attempt(request_id, "stem")
                self.repo.save_artifact(request_id, "STEM", nucleo.to_dict(), prov)
                self.repo.transition(request_id, None, Estado.STEM_GENERATED, "HAILA_LLM", "núcleo gerado", prov)
                stem_flags = avaliar_nucleo(nucleo, referencia.texto)
                if stem_flags:
                    feedback_nucleo = [f.to_dict() for f in stem_flags]
                    self.repo.record_flags(request_id, feedback_nucleo)
                    self.repo.transition(request_id, None, Estado.BLOCKED_BY_RED_FLAGS, "HAILA_RED_FLAGS", "núcleo bloqueado", {"red_flags": feedback_nucleo})
                    req = self.repo.get_request(request_id); nucleo = None
                    continue
            for _ in range(req["max_distractor_attempts"]):
                questao = None
                try:
                    distratores, prov_slm = distractor_generator(nucleo, feedback_distratores)
                except ValueError as exc:
                    self.repo.increment_attempt(request_id, "distractor")
                    flag = RedFlag(
                        "formatacao_quebrada", "DISTRATORES", "saida_slm",
                        f"distratores não puderam ser interpretados: {exc}", "DISTRATORES"
                    )
                    flags_saida = [flag.to_dict()]
                    # A próxima tentativa precisa receber a causa concreta da
                    # falha (por exemplo, "recebeu 2; esperado 4"). Sem isto,
                    # o SLM repete a mesma saída e o retorno final perde a
                    # explicação do esgotamento.
                    feedback_distratores = flags_saida
                    self.repo.record_flags(request_id, flags_saida)
                    self.repo.transition(
                        request_id, None, Estado.BLOCKED_BY_RED_FLAGS, "HAILA_RED_FLAGS",
                        "saída inválida do SLM; nova tentativa solicitada",
                        {"red_flags": flags_saida},
                    )
                    continue
                self.repo.increment_attempt(request_id, "distractor")
                self.repo.save_artifact(request_id, "DISTRACTORS", [d.to_dict() for d in distratores], prov_slm)
                self.repo.transition(request_id, None, Estado.DISTRACTORS_GENERATED, "HAILA_SLM", "distratores gerados", prov_slm)
                dflags = avaliar_distratores(nucleo, distratores)
                if not dflags:
                    questao = montar_item(nucleo, distratores, request_id)
                    version = self.repo.add_version(request_id, questao, {"rag_id": referencia.id, "llm": stem_generator.model, "slm": distractor_generator.model})
                    self.repo.transition(request_id, version["id"], Estado.ITEM_ASSEMBLED, "HAILA_ASSEMBLER", "item montado", {})
                    iflags = avaliar_item(questao)
                    if not iflags:
                        deterministic_flags, deterministic_prov = red_flag_analyzer(
                            questao, req["specification"], referencia.to_dict()
                        )
                        self.repo.save_artifact(request_id, "DETERMINISTIC_RED_FLAGS", [f.to_dict() for f in deterministic_flags], deterministic_prov)
                        iflags = deterministic_flags
                    if not iflags:
                        self.repo.transition(request_id, version["id"], Estado.GENERATION_COMPLETED, "HAILA_RED_FLAGS", "geração concluída sem red flags", {})
                        return {"request_id": request_id, "version": version, "state": Estado.GENERATION_COMPLETED.value, "red_flags": []}
                    # Cada flag informa qual componente deve repetir a geração.
                    if any(f.reparo == "NUCLEO" for f in iflags):
                        feedback_nucleo = [f.to_dict() for f in iflags]
                        self.repo.record_flags(request_id, feedback_nucleo)
                        self.repo.transition(request_id, version["id"], Estado.BLOCKED_BY_RED_FLAGS, "HAILA_RED_FLAGS", "conteúdo bloqueado", {"red_flags": feedback_nucleo})
                        req = self.repo.get_request(request_id); nucleo = None
                        break
                    dflags = iflags
                feedback_distratores = [f.to_dict() for f in dflags]
                # Preserve the actual rejected text even when the auditor does
                # not put it in quotation marks in its natural-language evidence.
                for flag in feedback_distratores:
                    match = re.fullmatch(r"alternativas\[(\d+)\]", flag.get("campo", ""))
                    if match and questao:
                        indice = int(match.group(1))
                        if 0 <= indice < len(questao["alternativas"]) and indice != questao["correta"]:
                            flag["alternativa_rejeitada"] = questao["alternativas"][indice]
                self.repo.record_flags(request_id, feedback_distratores)
                self.repo.transition(request_id, None, Estado.BLOCKED_BY_RED_FLAGS, "HAILA_RED_FLAGS", "distratores/item bloqueados", {"red_flags": feedback_distratores})

            if nucleo is None:
                continue
            # Esgotar tentativas locais do SLM não invalida o núcleo, mas encerra esta solicitação.
            self.repo.transition(request_id, None, Estado.ATTEMPTS_EXHAUSTED, "HAILA", "limite de tentativas do SLM atingido", {"red_flags": feedback_distratores})
            return {"request_id": request_id, "state": Estado.ATTEMPTS_EXHAUSTED.value, "red_flags": feedback_distratores}

        self.repo.transition(request_id, None, Estado.ATTEMPTS_EXHAUSTED, "HAILA", "limite de tentativas da LLM atingido", {"red_flags": feedback_nucleo})
        return {"request_id": request_id, "state": Estado.ATTEMPTS_EXHAUSTED.value, "red_flags": feedback_nucleo}

def montar_item(nucleo: NucleoQuestao, distratores: list[DistratorGerado], seed: str) -> dict[str, Any]:
    itens = [(nucleo.resposta_correta, None)] + [(d.texto, i) for i, d in enumerate(distratores)]
    rnd = random.Random(hashlib.sha256(seed.encode()).hexdigest())
    rnd.shuffle(itens)
    correta = next(i for i, (_, origem) in enumerate(itens) if origem is None)
    rastreio = [{"indice_final": i, "distrator_origem": origem} for i, (_, origem) in enumerate(itens) if origem is not None]
    return {"exame": "ENADE", "enunciado": nucleo.enunciado, "alternativas": [x[0] for x in itens],
            "correta": correta, "explicacao": nucleo.explicacao, "competencia": nucleo.competencia,
            "habilidade": nucleo.habilidade, "objeto_conhecimento": nucleo.objeto_conhecimento,
            "tem_imagem": nucleo.tem_imagem, "recurso_visual": nucleo.recurso_visual,
            "rastreio_distratores": rastreio}
