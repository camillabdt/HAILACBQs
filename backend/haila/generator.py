from __future__ import annotations

import ast
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Callable, Protocol

from .contracts import DistratorGerado, NucleoQuestao, ReferenciaRAG


class RecuperadorRAG(Protocol):
    def __call__(self, specification: dict[str, Any]) -> ReferenciaRAG: ...


class SpecificationRAG:
    """Adapter inicial: recebe uma referência recuperada externamente na solicitação."""
    def __call__(self, specification):
        ref = specification.get("referencia") or {}
        if not ref.get("id") or not ref.get("texto"):
            raise RuntimeError("solicitação não contém referencia.id e referencia.texto")
        return ReferenciaRAG(id=str(ref["id"]), texto=str(ref["texto"]), exame="ENADE",
                             ano=ref.get("ano"), metadados=ref.get("metadados") or {})


class GeradorNucleo(Protocol):
    model: str
    def __call__(self, specification: dict[str, Any], referencia: ReferenciaRAG,
                 feedback: list[dict[str, Any]]) -> tuple[NucleoQuestao, dict[str, Any]]: ...


class GeradorDistratores(Protocol):
    model: str
    def __call__(self, nucleo: NucleoQuestao, feedback: list[dict[str, Any]]) -> tuple[list[DistratorGerado], dict[str, Any]]: ...


SYSTEM_QUALITY_BASE = """Crie uma questão objetiva inédita de Computação, alinhada ao ENADE e à especificação.
Use a referência somente como fundamento conceitual. Exija raciocínio, mantenha uma
única resposta defensável e sustente-a na explicação. Delimite produto, API e modelo
de execução quando forem necessários. Não use comportamento indefinido. Formule o
comando afirmativamente, sem termos vagos ou absolutos. Não repita no enunciado a
expressão que entrega o gabarito. Respeite o objeto de conhecimento e responda somente
JSON válido."""


SYSTEM_NUCLEO = SYSTEM_QUALITY_BASE + """
Gere somente o núcleo: enunciado, resposta_correta concisa, explicacao, competencia,
habilidade, objeto_conhecimento, tem_imagem e recurso_visual. Não gere alternativas.
Ao comparar TCP e UDP, restrinja explicitamente a comparação aos dois protocolos e
use como resposta uma afirmação comparativa sobre ambos, sem copiá-la no enunciado.
Se o item reunir função e desempenho, pergunte separadamente pelo aspecto pretendido."""


INSTRUCAO_DISTRACTORES = (
    "Gere exatamente 4 distratores plausiveis, distintos entre si e "
    "diferentes da resposta correta. Responda somente JSON valido."
)

SYSTEM_DISTRACTORES_QWEN = (
    "Você gera distratores para questões educacionais em português. "
    "Produza exatamente quatro alternativas incorretas, plausíveis, relevantes, "
    "gramaticalmente corretas e do mesmo tipo conceitual e nível de especificidade "
    "do gabarito. Cada alternativa deve representar uma confusão real de estudante "
    "sobre o conceito cobrado. Evite recipientes ou categorias genéricas como "
    "'arquivo', 'sistema', 'banco de dados' ou 'lista' quando o gabarito nomeia uma "
    "estrutura, protocolo, propriedade ou mecanismo específico. Não copie, não "
    "parafraseie e não inclua o gabarito. Não invente palavras. Nunca devolva "
    "placeholders como <NAME>, traduções para outro idioma ou palavras soltas "
    "sem função de alternativa. Se o gabarito é uma propriedade, protocolo, "
    "estrutura, classe ou paradigma, todos os distratores devem pertencer à "
    "mesma categoria. Responda "
    "Mantenha as quatro alternativas com extensão e estrutura gramatical próximas "
    "às da resposta correta, para que o gabarito não se destaque pelo tamanho. "
    "exclusivamente com JSON válido no formato "
    '{"distratores":["D1","D2","D3","D4"]}.'
)


def resumir_feedback_distratores(red_flags):
    """Extrai somente alternativas citadas pelo auditor para orientar a nova amostra."""
    rejeitados = []
    vistos = set()
    for flag in red_flags or []:
        evidencia = str(flag.get("evidencia") or flag.get("evidence") or "")
        citados = re.findall(r'["\u201c]([^"\u201d]{2,160})["\u201d]', evidencia)
        if isinstance(flag.get("alternativa_rejeitada"), str):
            citados.insert(0, flag["alternativa_rejeitada"])
        for texto in citados:
            texto = re.sub(r"\s+", " ", texto).strip()
            chave = texto.casefold()
            if chave not in vistos:
                vistos.add(chave)
                rejeitados.append(texto)
    return rejeitados[:8]


def chave_semantica_curta(texto):
    """Chave conservadora para impedir cópia literal do gabarito na origem."""
    base = unicodedata.normalize("NFKD", str(texto or "").casefold())
    base = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"\W+", "", base)


def criar_prompt_distratores(enunciado, resposta, red_flags=None):
    """Prompt canônico compartilhado pelo fine-tuning e pela inferência local."""
    correcao = ""
    if red_flags:
        correcao = "\n\n### Corrija estes problemas:\n" + json.dumps(
            red_flags, ensure_ascii=False
        )
    return (
        f"### Instrucao:\n{INSTRUCAO_DISTRACTORES}\n\n"
        f"### Questao:\n{str(enunciado).strip()}\n\n"
        f"### Resposta correta:\n{str(resposta).strip()}\n\n"
        f"{correcao}\n\n### Saida:\n"
    )


class EnadeStemGenerator:
    def __init__(self, caller: Callable[[str, str], str], model: str = "desconhecido"):
        self.caller, self.model = caller, model

    def __call__(self, specification, referencia, feedback):
        reparo_prioritario = ""
        codigos = {str(item.get("codigo") or "") for item in feedback or []}
        if "selecao_de_protocolo_potencialmente_ambigua" in codigos:
            reparo_prioritario = (
                "CORREÇÃO OBRIGATÓRIA: não pergunte 'qual protocolo' e não use apenas "
                "TCP ou UDP como resposta. Pergunte: 'Considerando exclusivamente TCP "
                "e UDP, qual comparação descreve corretamente os serviços oferecidos?'. "
                "A resposta deve comparar ambos, por exemplo: 'TCP oferece entrega "
                "confiável e ordenada; UDP reduz a sobrecarga sem oferecer essas "
                "garantias'. Não repita a resposta no enunciado."
            )
        payload = {
            "solicitacao": specification,
            "referencia": referencia.to_dict(),
            "corrija": feedback,
            "reparo_prioritario": reparo_prioritario,
            "schema": {"enunciado": "string", "resposta_correta": "string", "explicacao": "string",
                       "competencia": "string", "habilidade": "string", "objeto_conhecimento": "string",
                       "tem_imagem": False, "recurso_visual": None},
        }
        pedido = json.dumps(payload, ensure_ascii=False)
        if reparo_prioritario:
            pedido = reparo_prioritario + "\n\n" + pedido
        data = json.loads(self.caller(SYSTEM_NUCLEO, pedido))
        token_usage = getattr(self.caller, "last_usage", None)
        if "dependencia_visual" in data:
            dependencia = data.pop("dependencia_visual")
            if isinstance(dependencia, dict):
                data.setdefault("tem_imagem", bool(dependencia.get("necessaria") or dependencia.get("tem_imagem")))
                data.setdefault("recurso_visual", dependencia.get("recurso") or dependencia.get("descricao"))
            elif isinstance(dependencia, bool):
                data.setdefault("tem_imagem", dependencia); data.setdefault("recurso_visual", None)
            elif dependencia:
                data.setdefault("tem_imagem", True); data.setdefault("recurso_visual", str(dependencia))
            else:
                data.setdefault("tem_imagem", False); data.setdefault("recurso_visual", None)
        proibidos = {"alternativas", "distratores", "correta"} & data.keys()
        if proibidos:
            raise ValueError(f"LLM violou o contrato do núcleo: {sorted(proibidos)}")
        provenance = {"modelo": self.model, "prompt_version": "enade-stem-1.1.0"}
        if token_usage: provenance["token_usage_remote"] = dict(token_usage)
        return NucleoQuestao(**data), provenance


class TinyLlamaLoraDistractorGenerator:
    """Adapter real e lazy para o TinyLlama + LoRA treinado para a HAILA."""
    def __init__(self, adapter_path: str | Path, base_model: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"):
        self.adapter_path, self.base_model = Path(adapter_path), base_model
        self.model = f"{base_model}+LoRA:{self.adapter_path.name}"
        self._pipeline = None

    def _load(self):
        if not self.adapter_path.exists():
            raise RuntimeError(f"adapter SLM não encontrado: {self.adapter_path}")
        try:
            from peft import PeftModel
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
        except ImportError as exc:
            raise RuntimeError("integração SLM requer transformers e peft") from exc
        tokenizer = AutoTokenizer.from_pretrained(str(self.adapter_path))
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        base = AutoModelForCausalLM.from_pretrained(
            self.base_model, torch_dtype=torch.float32, low_cpu_mem_usage=True
        )
        model = PeftModel.from_pretrained(base, str(self.adapter_path))
        model.eval()
        self._pipeline = pipeline("text-generation", model=model, tokenizer=tokenizer)

    def __call__(self, nucleo, feedback):
        if self._pipeline is None: self._load()
        # O LoRA foi ajustado com o prompt canônico, sem mensagens de reparo.
        # As red flags servem para rejeitar/amostrar novamente, não para mudar
        # a distribuição de entrada do modelo pequeno.
        prompt = criar_prompt_distratores(
            nucleo.enunciado,
            nucleo.resposta_correta,
            None,
        )
        raw = self._pipeline(
            prompt,
            max_new_tokens=int(os.getenv("HAILA_SLM_MAX_NEW_TOKENS", "512")),
            do_sample=True,
            temperature=float(os.getenv("HAILA_SLM_TEMPERATURE", "0.3")),
            top_p=float(os.getenv("HAILA_SLM_TOP_P", "0.85")),
            repetition_penalty=float(os.getenv("HAILA_SLM_REPETITION_PENALTY", "1.15")),
            no_repeat_ngram_size=int(os.getenv("HAILA_SLM_NO_REPEAT_NGRAM_SIZE", "3")),
            return_full_text=False,
        )[0]["generated_text"]
        data = _extrair_json(raw)
        distratores, normalizacoes = normalizar_distratores(data)
        return distratores, {"modelo": self.model, "adapter_path": str(self.adapter_path),
                             "normalizacoes": normalizacoes, "prompt_version": "slm-distractors-3.0.0"}


class QwenDistractorGenerator:
    """Qwen pequeno local, com LoRA opcional, usando o template de chat nativo."""
    def __init__(self, base_model: str, adapter_path: str | Path | None = None):
        self.base_model = base_model
        self.adapter_path = Path(adapter_path) if adapter_path else None
        sufixo = f"+LoRA:{self.adapter_path.name}" if self.adapter_path else ":base"
        self.model = f"{base_model}{sufixo}"
        self._model = None
        self._tokenizer = None

    def _load(self):
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("integração Qwen requer torch e transformers") from exc

        torch.set_num_threads(int(os.getenv("HAILA_SLM_THREADS", "4")))
        origem_tokenizer = str(self.adapter_path) if self.adapter_path else self.base_model
        self._tokenizer = AutoTokenizer.from_pretrained(origem_tokenizer, use_fast=True)
        self._tokenizer.pad_token = self._tokenizer.pad_token or self._tokenizer.eos_token
        base = AutoModelForCausalLM.from_pretrained(
            self.base_model,
            dtype=torch.float32,
            low_cpu_mem_usage=True,
        )
        if self.adapter_path:
            if not self.adapter_path.exists():
                raise RuntimeError(f"adapter Qwen não encontrado: {self.adapter_path}")
            from peft import PeftModel
            # Na inferência o adaptador é imutável. Fundi-lo no modelo-base
            # remove a camada PEFT de cada passo de geração e reduz a latência
            # em CPU sem alterar os pesos aprendidos.
            base = PeftModel.from_pretrained(base, str(self.adapter_path)).merge_and_unload()
        base.config.use_cache = True
        self._model = base.eval()

    def __call__(self, nucleo, feedback):
        if self._model is None:
            self._load()
        import torch

        # Mantemos o prompt idêntico ao usado no ajuste. Injetar a descrição
        # longa da falha anterior fez este modelo pequeno abandonar o schema.
        # Saídas parciais são acumuladas abaixo, sempre com rastreabilidade.
        usuario = criar_prompt_distratores(
            nucleo.enunciado,
            nucleo.resposta_correta,
            None,
        )
        rejeitados = resumir_feedback_distratores(feedback)
        instrucao_reparo = ""
        if rejeitados:
            instrucao_reparo = (
                " Esta é uma nova tentativa. Não repita estas alternativas "
                f"rejeitadas: {json.dumps(rejeitados, ensure_ascii=False)}. "
                "Substitua-as por erros conceituais diferentes e plausíveis."
            )
        texto = self._tokenizer.apply_chat_template(
            [
                {"role": "system", "content": SYSTEM_DISTRACTORES_QWEN + instrucao_reparo},
                {"role": "user", "content": usuario},
            ],
            tokenize=False,
            add_generation_prompt=True,
        )
        entrada = self._tokenizer(
            texto,
            return_tensors="pt",
            truncation=True,
            max_length=int(os.getenv("HAILA_SLM_MAX_INPUT_TOKENS", "2048")),
        )
        max_amostras = max(1, int(os.getenv("HAILA_QWEN_MAX_AMOSTRAS", "3")))
        tamanho_pool = max(4, int(os.getenv("HAILA_QWEN_CANDIDATE_POOL", "8")))
        acumulados: list[DistratorGerado] = []
        vistos: set[str] = {chave_semantica_curta(t) for t in rejeitados}
        chave_gabarito = chave_semantica_curta(nucleo.resposta_correta)
        normalizacoes: list[str] = []
        brutos: list[str] = []
        input_tokens_total = 0
        output_tokens_total = 0

        for numero_amostra in range(1, max_amostras + 1):
            with torch.inference_mode():
                ids = self._model.generate(
                    **entrada,
                    max_new_tokens=int(os.getenv("HAILA_SLM_MAX_NEW_TOKENS", "512")),
                    do_sample=True,
                    temperature=float(os.getenv("HAILA_SLM_TEMPERATURE", "0.3")),
                    top_p=float(os.getenv("HAILA_SLM_TOP_P", "0.85")),
                    repetition_penalty=float(os.getenv("HAILA_SLM_REPETITION_PENALTY", "1.15")),
                    no_repeat_ngram_size=int(os.getenv("HAILA_SLM_NO_REPEAT_NGRAM_SIZE", "3")),
                    pad_token_id=self._tokenizer.eos_token_id,
                )
            input_tokens_total += int(entrada["input_ids"].shape[1])
            output_tokens_total += int(ids.shape[1] - entrada["input_ids"].shape[1])
            bruto = self._tokenizer.decode(
                ids[0][entrada["input_ids"].shape[1]:],
                skip_special_tokens=True,
            )
            brutos.append(bruto)
            try:
                data = _extrair_json(bruto)
            except ValueError:
                continue

            try:
                parciais, reparos = normalizar_distratores_parciais(data)
            except ValueError:
                continue
            normalizacoes.extend(
                f"amostra_{numero_amostra}:{reparo}" for reparo in reparos
            )
            for distrator in parciais:
                if re.search(r"<\s*[A-Z][A-Z0-9_-]*\s*>", distrator.texto):
                    normalizacoes.append(
                        f"amostra_{numero_amostra}:placeholder_descartado"
                    )
                    continue
                chave = chave_semantica_curta(distrator.texto)
                if chave and chave == chave_gabarito:
                    normalizacoes.append(
                        f"amostra_{numero_amostra}:copia_do_gabarito_descartada"
                    )
                    continue
                if chave and chave not in vistos:
                    vistos.add(chave)
                    acumulados.append(distrator)
            if len(acumulados) >= tamanho_pool:
                break

        if len(acumulados) >= 4:
            return acumulados[:tamanho_pool], {
                "modelo": self.model,
                "adapter_path": str(self.adapter_path) if self.adapter_path else None,
                "normalizacoes": normalizacoes,
                "amostras": len(brutos),
                "candidatos_gerados": len(acumulados[:tamanho_pool]),
                "feedback_aplicado": bool(rejeitados),
                "alternativas_rejeitadas": rejeitados,
                "prompt_version": "qwen-distractors-1.4.0",
                "token_usage_local": {
                    "input_tokens": input_tokens_total,
                    "output_tokens": output_tokens_total,
                    "total_tokens": input_tokens_total + output_tokens_total,
                },
            }

        amostras_brutas = [texto.strip().replace("\n", " ")[:180] for texto in brutos]
        raise ValueError(
            "Qwen não reuniu 4 distratores distintos; "
            f"candidatos={len(acumulados)}; amostras={max_amostras}; "
            f"inicios={amostras_brutas!r}"
        )


class GroqBestOfNSelector:
    """Seleciona quatro itens de um pool criado exclusivamente pela SLM."""
    def __init__(self, caller, model):
        self.caller, self.model = caller, model

    def __call__(self, nucleo, candidatos):
        payload = {
            "enunciado": nucleo.enunciado,
            "resposta_correta": nucleo.resposta_correta,
            "candidatos": [
                {"indice": indice, "texto": candidato.texto}
                for indice, candidato in enumerate(candidatos)
            ],
            "schema": {"indices": ["quatro inteiros distintos"]},
        }
        system = (
            "Você é o seletor de candidatos da HAILA. A SLM já gerou todos os "
            "candidatos; você não pode criar nem reescrever alternativas. Escolha "
            "exatamente quatro índices. Priorize conceitos reais, incorretos para o "
            "cenário, plausíveis para estudantes, relevantes e distintos. Exclua "
            "cópias ou paráfrases do gabarito, palavras inventadas, erros gramaticais, "
            "alternativas vagas e possíveis respostas corretas. Responda apenas JSON."
        )
        data = json.loads(self.caller(system, json.dumps(payload, ensure_ascii=False)))
        indices = data.get("indices")
        if not isinstance(indices, list) or len(indices) != 4:
            raise ValueError("seletor semântico não devolveu quatro índices")
        if any(type(i) is not int or i < 0 or i >= len(candidatos) for i in indices):
            raise ValueError("seletor semântico devolveu índice inválido")
        if len(set(indices)) != 4:
            raise ValueError("seletor semântico repetiu índices")
        return [candidatos[i] for i in indices], {
            "modelo": self.model,
            "indices_selecionados": indices,
        }


class DeterministicPoolSelector:
    """Escolhe quatro candidatos da SLM sem gerar ou reescrever conteúdo."""
    model = "deterministic-pool-selector-v1"

    @staticmethod
    def _palavras(texto: str) -> list[str]:
        base = unicodedata.normalize("NFKD", str(texto).casefold())
        base = "".join(c for c in base if not unicodedata.combining(c))
        return re.findall(r"[a-z0-9]+", base)

    def __call__(self, nucleo, candidatos):
        tamanho_gabarito = max(1, len(self._palavras(nucleo.resposta_correta)))
        pontuados = []
        for indice, candidato in enumerate(candidatos):
            palavras = self._palavras(candidato.texto)
            tamanho = max(1, len(palavras))
            # Premia paralelismo de extensão e conteúdo específico. O índice
            # estabiliza empates para que a mesma entrada produza a mesma saída.
            desvio = abs(tamanho - tamanho_gabarito) / tamanho_gabarito
            especificidade = len(set(palavras)) / tamanho
            pontuados.append((desvio, -especificidade, indice))
        indices = [indice for _, _, indice in sorted(pontuados)[:4]]
        if len(indices) != 4:
            raise ValueError("pool da SLM não contém quatro candidatos selecionáveis")
        return [candidatos[i] for i in indices], {
            "modelo": self.model,
            "indices_selecionados": indices,
            "criterio": "paralelismo_de_extensao_e_especificidade_lexical",
        }


class BestOfNDistractorGenerator:
    """Gera N pela SLM e reduz para quatro sem permitir criação pelo seletor."""
    def __init__(self, generator, selector):
        self.generator, self.selector = generator, selector
        self.model = f"best-of-n({getattr(generator, 'model', 'slm')})"

    def __call__(self, nucleo, feedback):
        candidatos, provenance = self.generator(nucleo, feedback)
        if len(candidatos) == 4:
            return candidatos, dict(provenance, selecao="pool_exato")
        escolhidos, selecao = self.selector(nucleo, candidatos)
        tipo_selecao = (
            "deterministic_best_of_n"
            if getattr(self.selector, "model", "").startswith("deterministic-")
            else "groq_best_of_n"
        )
        return escolhidos, dict(
            provenance,
            selecao=tipo_selecao,
            candidatos_no_pool=len(candidatos),
            seletor=selecao,
        )


def _extrair_json(raw: str) -> Any:
    """Recupera a estrutura mesmo quando o SLM repete texto após o primeiro JSON."""
    decoder = json.JSONDecoder()
    for inicio, caractere in enumerate(raw):
        if caractere not in "[{":
            continue
        try:
            data, _ = decoder.raw_decode(raw[inicio:])
            if isinstance(data, (dict, list)):
                return data
        except json.JSONDecodeError:
            pass

    # Alguns modelos pequenos devolvem a representação Python com aspas
    # simples. literal_eval é restrito a literais e não executa código.
    candidatos = []
    for abertura, fechamento in (("{", "}"), ("[", "]")):
        inicio, fim = raw.find(abertura), raw.rfind(fechamento)
        if inicio >= 0 and fim >= inicio:
            candidatos.append(raw[inicio:fim + 1])
    for candidato in candidatos:
        try:
            data = ast.literal_eval(candidato)
            if isinstance(data, (dict, list)):
                return data
        except (SyntaxError, ValueError):
            pass

    # Último recurso controlado: quatro linhas numeradas ou com marcadores.
    linhas = []
    padrao = re.compile(r"^\s*(?:\d+\s*[\).:\-]|[-*])\s*(.+?)\s*$")
    for linha in raw.splitlines():
        achado = padrao.match(linha)
        if achado:
            texto = achado.group(1).strip().rstrip(",").strip().strip("\"'")
            if texto:
                linhas.append(texto)
    if len(linhas) == 4:
        return linhas

    amostra = raw.strip().replace("\n", " ")[:240]
    raise ValueError(f"SLM não devolveu JSON de distratores válido; início={amostra!r}")


def normalizar_distratores(data: Any) -> tuple[list[DistratorGerado], list[str]]:
    saida, normalizacoes = normalizar_distratores_parciais(data)
    if len(saida) != 4:
        raise ValueError(
            f"SLM deve devolver exatamente 4 distratores; recebeu {len(saida)}"
        )
    return saida, normalizacoes


def normalizar_distratores_parciais(data: Any) -> tuple[list[DistratorGerado], list[str]]:
    """Normaliza de zero a N candidatos; o contrato exato é aplicado acima."""
    normalizacoes: list[str] = []
    if isinstance(data, dict):
        for chave in ("distratores", "distratos", "distrators", "distrutores", "alternativas"):
            if chave in data:
                data = data[chave]
                if chave != "distratores": normalizacoes.append(f"{chave}->distratores")
                break
    if not isinstance(data, list): raise ValueError("saída SLM não contém lista de distratores")
    saida = []
    for item in data:
        if isinstance(item, str):
            normalizacoes.append("string->objeto")
            item = {"texto": item}
        if not isinstance(item, dict): raise ValueError("distrator malformado")
        texto = item.get("texto") or item.get("distrator") or item.get("alternativa")
        if not texto: raise ValueError("distrator sem texto")
        saida.append(DistratorGerado(str(texto).strip(), str(item.get("erro", "")).strip(),
                                      str(item.get("por_que_e_falso", "")).strip()))
    return saida, normalizacoes


def stem_generator_from_env() -> EnadeStemGenerator:
    key = os.getenv("GROQ_API_KEY")
    if not key: raise RuntimeError("GROQ_API_KEY não configurada")
    from openai import OpenAI
    model = os.getenv("HAILA_STEM_MODEL", "openai/gpt-oss-120b")
    client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1",
                    timeout=float(os.getenv("HAILA_GROQ_TIMEOUT_SECONDS", "60")), max_retries=0)
    def call(system, user):
        r = client.chat.completions.create(model=model, messages=[{"role":"system","content":system},{"role":"user","content":user}],
                                           temperature=0.7, response_format={"type":"json_object"})
        usage = getattr(r, "usage", None)
        call.last_usage = {
            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        }
        return r.choices[0].message.content or "{}"
    call.last_usage = None
    return EnadeStemGenerator(call, model)


_LOCAL_SLM_CACHE: dict[tuple[str, str, str], Any] = {}


def slm_generator_from_env() -> TinyLlamaLoraDistractorGenerator:
    from .hybrid import HybridDistractorGenerator
    backend = os.getenv("HAILA_SLM_BACKEND", "qwen").strip().casefold()
    path = os.getenv("HAILA_SLM_ADAPTER_PATH", "").strip() or None
    base_model = os.getenv(
        "HAILA_SLM_BASE_MODEL",
        "Qwen/Qwen2.5-1.5B-Instruct" if backend == "qwen" else "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    )
    if backend not in {"qwen", "tinyllama"}:
        raise RuntimeError(f"HAILA_SLM_BACKEND inválido: {backend!r}")
    if backend == "tinyllama" and not path:
        raise RuntimeError("HAILA_SLM_ADAPTER_PATH não configurado para TinyLlama")

    use_memory = os.getenv("HAILA_USE_CURATED_MEMORY", "1") == "1"
    use_rules = os.getenv("HAILA_USE_DETERMINISTIC_DISTRACTOR_RULES", "1") == "1"
    cache_key = (backend, base_model, path or "", use_memory, use_rules)
    hibrido = _LOCAL_SLM_CACHE.get(cache_key)
    if hibrido is None:
        slm = (
            QwenDistractorGenerator(base_model, path)
            if backend == "qwen"
            else TinyLlamaLoraDistractorGenerator(path, base_model)
        )
        hibrido = HybridDistractorGenerator(slm, use_memory=use_memory, use_rules=use_rules)
        _LOCAL_SLM_CACHE[cache_key] = hibrido
    return BestOfNDistractorGenerator(hibrido, DeterministicPoolSelector())
