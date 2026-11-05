from __future__ import annotations

import hashlib
import os
import random
import re
import unicodedata
from typing import Any

from .contracts import DistratorGerado, NucleoQuestao, RedFlag, ReferenciaRAG
from .domain import ESTADOS_TERMINAIS, TRANSICOES_PERMITIDAS, Estado
from .repository import HailaRepository
from .structural import avaliar_distratores, avaliar_item, avaliar_nucleo


_FATAL_STEM_CODES = {
    "enunciado_ausente_ou_curto",
    "resposta_correta_ausente",
    "explicacao_ausente",
    "dependencia_visual_ausente",
    "formatacao_quebrada",
}


def _is_transient_provider_error(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    name = exc.__class__.__name__
    return status == 429 or name in {
        "RateLimitError",
        "APITimeoutError",
        "APIConnectionError",
    }


def _candidate_key(texto: str) -> str:
    base = unicodedata.normalize("NFKD", str(texto or "").casefold())
    base = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"\W+", "", base)


def _flag_dict(flag: RedFlag, rejected_text: str | None = None) -> dict[str, Any]:
    data = flag.to_dict()
    if rejected_text:
        data["alternativa_rejeitada"] = rejected_text
    return data


def _candidate_flags(nucleo: NucleoQuestao, candidato: DistratorGerado) -> list[RedFlag]:
    """Validate one candidate while ignoring the collection-size contract."""
    return [
        flag
        for flag in avaliar_distratores(nucleo, [candidato])
        if flag.codigo != "quantidade_distratores_invalida"
    ]


def _flagged_indices(flags: list[RedFlag], question: dict[str, Any]) -> set[int]:
    """Map item/distractor flags back to final alternative indices when possible."""
    indices: set[int] = set()
    correta = question.get("correta")
    alternativas = question.get("alternativas") or []
    for flag in flags:
        match = re.fullmatch(r"(?:distratores|alternativas)\[(\d+)\]", flag.campo or "")
        if match:
            idx = int(match.group(1))
            # structural distractor indices are local to the selected four;
            # final item indices are handled via evidence below.
            indices.add(idx)
        for raw in re.findall(r"(?:^|[;\s])(\d+):(?:\"|')", flag.evidencia or ""):
            indices.add(int(raw))
    return {i for i in indices if i >= 0 and i < max(4, len(alternativas)) and i != correta}


class HailaOrchestrator:
    """Sustainable HAILA pipeline with checkpoints and incremental distractor reuse."""

    def __init__(self, repository: HailaRepository):
        self.repo = repository

    def solicitar(
        self,
        solicitante_id: str,
        specification: dict,
        max_attempts: int = 3,
        max_distractor_attempts: int = 3,
    ) -> dict:
        if min(max_attempts, max_distractor_attempts) < 1:
            raise ValueError("limites devem ser positivos")
        rid = self.repo.create_request(
            solicitante_id,
            specification,
            max_attempts,
            max_distractor_attempts,
        )
        return self.repo.get_request(rid)

    def _transition_if_possible(
        self,
        request_id: str,
        version_id: str | None,
        to_state: Estado,
        component: str,
        reason: str,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        current = Estado(self.repo.get_request(request_id)["state"])
        if current == to_state:
            return
        if to_state in TRANSICOES_PERMITIDAS.get(current, set()):
            self.repo.transition(
                request_id,
                version_id,
                to_state,
                component,
                reason,
                evidence or {},
            )

    def executar(
        self,
        request_id: str,
        rag,
        stem_generator,
        distractor_generator,
        red_flag_analyzer,
        jev_evaluator=None,
    ) -> dict:
        """Run or resume a request without discarding validated work.

        Transient provider errors are deliberately *not* terminal. The reference,
        stem checkpoint and distractor bank already persisted in SQLite remain
        available; a later call to /generate resumes from the last checkpoint.
        """
        try:
            sustainable = os.getenv("HAILA_SUSTAINABLE_PIPELINE", "1") == "1"
            runner = self._executar if sustainable else self._executar_legacy
            return runner(
                request_id,
                rag,
                stem_generator,
                distractor_generator,
                red_flag_analyzer,
                jev_evaluator,
            )
        except Exception as exc:
            if _is_transient_provider_error(exc):
                raise
            try:
                atual = Estado(self.repo.get_request(request_id)["state"])
                if atual not in ESTADOS_TERMINAIS:
                    self.repo.transition(
                        request_id,
                        None,
                        Estado.GENERATION_FAILED,
                        "HAILA",
                        "execução interrompida por exceção",
                        {
                            "excecao": type(exc).__name__,
                            "mensagem": str(exc)[:500],
                            "checkpoints_preservados": True,
                        },
                    )
            except Exception:
                pass
            raise

    def _executar_legacy(
        self,
        request_id: str,
        rag,
        stem_generator,
        distractor_generator,
        red_flag_analyzer,
        jev_evaluator=None,
    ) -> dict:
        """Original retry/reset pipeline kept for experiment reproducibility."""
        req = self.repo.get_request(request_id)
        referencia: ReferenciaRAG = rag(req["specification"])
        self.repo.save_artifact(request_id, "REFERENCE", referencia.to_dict(), {})
        self.repo.transition(
            request_id,
            None,
            Estado.REFERENCE_RETRIEVED,
            "HAILA_RAG",
            "referência recuperada",
            {"id": referencia.id},
        )
        feedback_nucleo, feedback_distratores = [], []
        nucleo: NucleoQuestao | None = None

        while req["stem_attempts"] < req["max_attempts"]:
            if nucleo is None:
                try:
                    nucleo, prov = stem_generator(
                        req["specification"], referencia, feedback_nucleo
                    )
                except ValueError as exc:
                    self.repo.increment_attempt(request_id, "stem")
                    flag = RedFlag(
                        "formatacao_quebrada",
                        "NUCLEO",
                        "saida_llm",
                        f"núcleo não pôde ser interpretado: {exc}",
                        "NUCLEO",
                    )
                    feedback_nucleo = [flag.to_dict()]
                    self.repo.record_flags(request_id, feedback_nucleo)
                    self.repo.transition(
                        request_id,
                        None,
                        Estado.BLOCKED_BY_RED_FLAGS,
                        "HAILA_RED_FLAGS",
                        "saída inválida da LLM; nova tentativa solicitada",
                        {"red_flags": feedback_nucleo},
                    )
                    req = self.repo.get_request(request_id)
                    continue
                self.repo.increment_attempt(request_id, "stem")
                self.repo.save_artifact(request_id, "STEM", nucleo.to_dict(), prov)
                self.repo.transition(
                    request_id,
                    None,
                    Estado.STEM_GENERATED,
                    "HAILA_LLM",
                    "núcleo gerado",
                    prov,
                )
                stem_flags = avaliar_nucleo(nucleo, referencia.texto)
                if stem_flags:
                    feedback_nucleo = [f.to_dict() for f in stem_flags]
                    self.repo.record_flags(request_id, feedback_nucleo)
                    self.repo.transition(
                        request_id,
                        None,
                        Estado.BLOCKED_BY_RED_FLAGS,
                        "HAILA_RED_FLAGS",
                        "núcleo bloqueado",
                        {"red_flags": feedback_nucleo},
                    )
                    req = self.repo.get_request(request_id)
                    nucleo = None
                    continue
            for _ in range(req["max_distractor_attempts"]):
                questao = None
                try:
                    distratores, prov_slm = distractor_generator(
                        nucleo, feedback_distratores
                    )
                except ValueError as exc:
                    self.repo.increment_attempt(request_id, "distractor")
                    flag = RedFlag(
                        "formatacao_quebrada",
                        "DISTRATORES",
                        "saida_slm",
                        f"distratores não puderam ser interpretados: {exc}",
                        "DISTRATORES",
                    )
                    flags_saida = [flag.to_dict()]
                    feedback_distratores = flags_saida
                    self.repo.record_flags(request_id, flags_saida)
                    self.repo.transition(
                        request_id,
                        None,
                        Estado.BLOCKED_BY_RED_FLAGS,
                        "HAILA_RED_FLAGS",
                        "saída inválida do SLM; nova tentativa solicitada",
                        {"red_flags": flags_saida},
                    )
                    continue
                self.repo.increment_attempt(request_id, "distractor")
                self.repo.save_artifact(
                    request_id,
                    "DISTRACTORS",
                    [d.to_dict() for d in distratores],
                    prov_slm,
                )
                self.repo.transition(
                    request_id,
                    None,
                    Estado.DISTRACTORS_GENERATED,
                    "HAILA_SLM",
                    "distratores gerados",
                    prov_slm,
                )
                dflags = avaliar_distratores(nucleo, distratores)
                if not dflags:
                    questao = montar_item(nucleo, distratores, request_id)
                    version = self.repo.add_version(
                        request_id,
                        questao,
                        {
                            "rag_id": referencia.id,
                            "llm": stem_generator.model,
                            "slm": distractor_generator.model,
                        },
                    )
                    self.repo.transition(
                        request_id,
                        version["id"],
                        Estado.ITEM_ASSEMBLED,
                        "HAILA_ASSEMBLER",
                        "item montado",
                        {},
                    )
                    iflags = avaliar_item(questao)
                    if not iflags:
                        deterministic_flags, deterministic_prov = red_flag_analyzer(
                            questao,
                            req["specification"],
                            referencia.to_dict(),
                        )
                        self.repo.save_artifact(
                            request_id,
                            "DETERMINISTIC_RED_FLAGS",
                            [f.to_dict() for f in deterministic_flags],
                            deterministic_prov,
                        )
                        iflags = deterministic_flags
                    jev_completed = False
                    if not iflags and jev_evaluator is not None:
                        try:
                            jev_result, jev_prov = jev_evaluator(
                                questao,
                                req["specification"],
                                referencia.to_dict(),
                            )
                            self.repo.save_artifact(
                                request_id,
                                "JEV_SEMANTIC_EVALUATION",
                                jev_result,
                                jev_prov,
                            )
                            jev_completed = True
                            jev_flags = jev_evaluator.blocking_flags(jev_result)
                            if jev_flags:
                                iflags = jev_flags
                        except Exception as exc:
                            self.repo.save_artifact(
                                request_id,
                                "JEV_ERROR",
                                {
                                    "type": type(exc).__name__,
                                    "message": str(exc)[:800],
                                },
                                {
                                    "provider": "typesafe",
                                    "mode": getattr(jev_evaluator, "mode", "unknown"),
                                },
                            )
                            if getattr(jev_evaluator, "fail_policy", "continue") == "error":
                                raise

                    if not iflags:
                        component = "HAILA_JEV" if jev_completed else "HAILA_RED_FLAGS"
                        reason = (
                            "geração concluída após avaliação semântica Jev"
                            if jev_completed
                            else "geração concluída sem red flags"
                        )
                        self.repo.transition(
                            request_id,
                            version["id"],
                            Estado.GENERATION_COMPLETED,
                            component,
                            reason,
                            {},
                        )
                        return {
                            "request_id": request_id,
                            "version": version,
                            "state": Estado.GENERATION_COMPLETED.value,
                            "red_flags": [],
                        }
                    if any(f.reparo == "NUCLEO" for f in iflags):
                        feedback_nucleo = [f.to_dict() for f in iflags]
                        self.repo.record_flags(request_id, feedback_nucleo)
                        self.repo.transition(
                            request_id,
                            version["id"],
                            Estado.BLOCKED_BY_RED_FLAGS,
                            "HAILA_RED_FLAGS",
                            "conteúdo bloqueado",
                            {"red_flags": feedback_nucleo},
                        )
                        req = self.repo.get_request(request_id)
                        nucleo = None
                        break
                    dflags = iflags
                feedback_distratores = [f.to_dict() for f in dflags]
                for flag in feedback_distratores:
                    match = re.fullmatch(
                        r"alternativas\[(\d+)\]", flag.get("campo", "")
                    )
                    if match and questao:
                        indice = int(match.group(1))
                        if (
                            0 <= indice < len(questao["alternativas"])
                            and indice != questao["correta"]
                        ):
                            flag["alternativa_rejeitada"] = questao["alternativas"][indice]
                self.repo.record_flags(request_id, feedback_distratores)
                self.repo.transition(
                    request_id,
                    None,
                    Estado.BLOCKED_BY_RED_FLAGS,
                    "HAILA_RED_FLAGS",
                    "distratores/item bloqueados",
                    {"red_flags": feedback_distratores},
                )

            if nucleo is None:
                continue
            self.repo.transition(
                request_id,
                None,
                Estado.ATTEMPTS_EXHAUSTED,
                "HAILA",
                "limite de tentativas do SLM atingido",
                {"red_flags": feedback_distratores},
            )
            return {
                "request_id": request_id,
                "state": Estado.ATTEMPTS_EXHAUSTED.value,
                "red_flags": feedback_distratores,
            }

        self.repo.transition(
            request_id,
            None,
            Estado.ATTEMPTS_EXHAUSTED,
            "HAILA",
            "limite de tentativas da LLM atingido",
            {"red_flags": feedback_nucleo},
        )
        return {
            "request_id": request_id,
            "state": Estado.ATTEMPTS_EXHAUSTED.value,
            "red_flags": feedback_nucleo,
        }

    def _load_reference(self, request_id: str, req: dict, rag) -> ReferenciaRAG:
        checkpoint = self.repo.latest_artifact(request_id, "REFERENCE")
        if checkpoint is not None:
            referencia = ReferenciaRAG(**checkpoint["payload"])
            self._transition_if_possible(
                request_id,
                None,
                Estado.REFERENCE_RETRIEVED,
                "HAILA_RAG",
                "referência recuperada de checkpoint",
                {"id": referencia.id, "checkpoint": True},
            )
            return referencia

        referencia: ReferenciaRAG = rag(req["specification"])
        self.repo.save_artifact(request_id, "REFERENCE", referencia.to_dict(), {})
        self._transition_if_possible(
            request_id,
            None,
            Estado.REFERENCE_RETRIEVED,
            "HAILA_RAG",
            "referência recuperada",
            {"id": referencia.id},
        )
        return referencia

    def _load_or_generate_stem(
        self,
        request_id: str,
        req: dict,
        referencia: ReferenciaRAG,
        stem_generator,
    ) -> tuple[NucleoQuestao, list[RedFlag]]:
        checkpoint = self.repo.latest_artifact(request_id, "STEM_CHECKPOINT")
        if checkpoint is not None:
            nucleo = NucleoQuestao(**checkpoint["payload"])
            flags = [
                RedFlag(**item)
                for item in checkpoint["provenance"].get("quality_flags", [])
                if isinstance(item, dict)
                and {"codigo", "etapa", "campo", "evidencia", "reparo"} <= set(item)
            ]
            self._transition_if_possible(
                request_id,
                None,
                Estado.STEM_GENERATED,
                "HAILA_LLM",
                "núcleo reutilizado de checkpoint",
                {"checkpoint": True},
            )
            return nucleo, flags

        # Interactive sustainable mode: one remote LLM generation per question.
        nucleo, prov = stem_generator(req["specification"], referencia, [])
        self.repo.increment_attempt(request_id, "stem")
        self.repo.save_artifact(request_id, "STEM", nucleo.to_dict(), prov)
        self._transition_if_possible(
            request_id,
            None,
            Estado.STEM_GENERATED,
            "HAILA_LLM",
            "núcleo gerado",
            prov,
        )

        flags = avaliar_nucleo(nucleo, referencia.texto)
        if flags:
            payload = [f.to_dict() for f in flags]
            self.repo.record_flags(request_id, payload)
            self.repo.save_artifact(
                request_id,
                "STEM_QUALITY_FLAGS",
                payload,
                {"blocking_policy": "essential_fields_only"},
            )

        fatais = [f for f in flags if f.codigo in _FATAL_STEM_CODES]
        if fatais:
            raise RuntimeError(
                "núcleo sem campos essenciais para montagem: "
                + ", ".join(sorted({f.codigo for f in fatais}))
            )

        self.repo.save_artifact(
            request_id,
            "STEM_CHECKPOINT",
            nucleo.to_dict(),
            {
                **prov,
                "locked": True,
                "quality_flags": [f.to_dict() for f in flags],
                "policy": "one_remote_stem_then_local_incremental_completion",
            },
        )
        return nucleo, flags

    def _load_pool(self, request_id: str) -> list[DistratorGerado]:
        raw = self.repo.load_distractor_pool(request_id)
        pool: list[DistratorGerado] = []
        vistos = set()
        for item in raw:
            try:
                candidato = DistratorGerado(**item)
            except TypeError:
                continue
            key = _candidate_key(candidato.texto)
            if key and key not in vistos:
                vistos.add(key)
                pool.append(candidato)
        return pool

    def _rejected_texts(self, request_id: str) -> list[str]:
        out = []
        vistos = set()
        kinds = (
            "DISTRACTOR_CANDIDATE_REJECTED",
            "DISTRACTOR_CANDIDATE_REJECTED_SEMANTIC",
            "DISTRACTOR_CANDIDATE_REJECTED_QUALITY",
        )
        for kind in kinds:
            for artifact in self.repo.artifacts_by_kind(request_id, kind):
                texto = str((artifact.get("payload") or {}).get("texto") or "").strip()
                key = _candidate_key(texto)
                if texto and key not in vistos:
                    vistos.add(key)
                    out.append(texto)
        return out

    def _grow_pool(
        self,
        request_id: str,
        req: dict,
        nucleo: NucleoQuestao,
        distractor_generator,
        feedback: list[dict[str, Any]],
        pool: list[DistratorGerado],
    ) -> tuple[list[DistratorGerado], list[dict[str, Any]]]:
        """Grow the persistent bank until four active candidates exist.

        Candidates beyond the first four that arrive in the *same already-paid
        batch* are preserved as a small reserve bank. We never make an extra SLM
        call just to create reserves. If the quality gate later removes one active
        candidate, a reserve is promoted before another Qwen call is considered.
        """
        no_progress_limit = max(
            2,
            int(os.getenv("HAILA_INCREMENTAL_MAX_NO_PROGRESS", "4")),
        )
        bank_max = max(4, int(os.getenv("HAILA_DISTRACTOR_BANK_MAX", "6")))
        no_progress = 0
        round_no = 0
        rejected = self._rejected_texts(request_id)
        known = {_candidate_key(d.texto) for d in pool}
        rejected_keys = {_candidate_key(x) for x in rejected}

        while len(pool) < 4:
            round_no += 1
            missing = 4 - len(pool)
            avoid = [d.texto for d in pool] + rejected
            try:
                if hasattr(distractor_generator, "generate_candidates"):
                    candidates, prov = distractor_generator.generate_candidates(
                        nucleo,
                        feedback,
                        target_count=missing,
                        avoid_texts=avoid,
                        max_samples=1,
                    )
                else:
                    candidates, prov = distractor_generator(nucleo, feedback)
            except ValueError as exc:
                self.repo.increment_attempt(request_id, "distractor")
                self.repo.save_artifact(
                    request_id,
                    "DISTRACTOR_BATCH_ERROR",
                    {"message": str(exc)[:1200], "missing": missing},
                    {"round": round_no, "pool_size": len(pool)},
                )
                feedback = [
                    {
                        "codigo": "lote_sem_candidato_utilizavel",
                        "etapa": "DISTRATORES",
                        "campo": "saida_slm",
                        "evidencia": str(exc)[:700],
                        "reparo": "DISTRATORES",
                    }
                ]
                no_progress += 1
                if no_progress >= no_progress_limit:
                    raise RuntimeError(
                        "SLM local ficou sem progresso; "
                        f"pool preservado={len(pool)}/4 após {round_no} rodadas"
                    ) from exc
                continue

            self.repo.increment_attempt(request_id, "distractor")
            self.repo.save_artifact(
                request_id,
                "DISTRACTOR_BATCH",
                [d.to_dict() for d in candidates],
                {**prov, "round": round_no, "missing_before": missing},
            )

            accepted_this_round = 0
            round_feedback: list[dict[str, Any]] = []
            for index, candidato in enumerate(candidates):
                if len(pool) >= bank_max:
                    self.repo.save_artifact(
                        request_id,
                        "DISTRACTOR_CANDIDATE_UNUSED_CAPACITY",
                        candidato.to_dict(),
                        {
                            "round": round_no,
                            "index": index,
                            "reason": "candidate_bank_capacity_reached",
                            "bank_max": bank_max,
                        },
                    )
                    continue

                key = _candidate_key(candidato.texto)
                if not key or key in known or key in rejected_keys:
                    continue

                flags = _candidate_flags(nucleo, candidato)
                if flags:
                    rejected.append(candidato.texto)
                    rejected_keys.add(key)
                    flag_payload = [
                        _flag_dict(flag, candidato.texto)
                        for flag in flags
                    ]
                    round_feedback.extend(flag_payload)
                    self.repo.record_flags(request_id, flag_payload)
                    self.repo.save_artifact(
                        request_id,
                        "DISTRACTOR_CANDIDATE_REJECTED",
                        candidato.to_dict(),
                        {
                            "round": round_no,
                            "index": index,
                            "flags": flag_payload,
                            "source": prov,
                        },
                    )
                    continue

                role = "active" if len(pool) < 4 else "reserve"
                known.add(key)
                pool.append(candidato)
                accepted_this_round += 1
                self.repo.save_artifact(
                    request_id,
                    (
                        "DISTRACTOR_CANDIDATE_ACCEPTED"
                        if role == "active"
                        else "DISTRACTOR_CANDIDATE_RESERVE"
                    ),
                    candidato.to_dict(),
                    {
                        "round": round_no,
                        "index": index,
                        "role": role,
                        "source": prov,
                    },
                )
                self.repo.save_distractor_pool(
                    request_id,
                    pool,
                    {
                        "round": round_no,
                        "accepted_total": len(pool),
                        "active_count": min(len(pool), 4),
                        "reserve_count": max(0, len(pool) - 4),
                        "required": 4,
                        "bank_max": bank_max,
                    },
                )

            if accepted_this_round:
                no_progress = 0
            else:
                no_progress += 1
            feedback = round_feedback or feedback

            if no_progress >= no_progress_limit:
                raise RuntimeError(
                    "SLM local produziu lotes, mas nenhum candidato novo foi aceito; "
                    f"pool preservado={len(pool)}/4"
                )

        return pool, feedback


    def _quality_gate_pool(
        self,
        request_id: str,
        req: dict,
        nucleo: NucleoQuestao,
        distractor_generator,
        pool: list[DistratorGerado],
        feedback: list[dict[str, Any]],
    ) -> tuple[
        list[DistratorGerado],
        list[dict[str, Any]],
        list[RedFlag],
        dict[str, Any],
    ]:
        """Validate terminology, plausibility and answer uniqueness locally.

        Only the affected candidate is removed. Existing active candidates and
        reserves survive. Reserves are promoted before another local SLM call,
        which avoids recomputation. The gate never calls the remote stem LLM.
        """
        enabled = os.getenv(
            "HAILA_DISTRACTOR_QUALITY_GATE",
            os.getenv("HAILA_LOCAL_SEMANTIC_GATE", "1"),
        ) == "1"
        validator = None
        if hasattr(distractor_generator, "validate_candidates_quality"):
            validator = distractor_generator.validate_candidates_quality
        elif hasattr(distractor_generator, "validate_candidates_semantically"):
            validator = distractor_generator.validate_candidates_semantically

        if not enabled or validator is None:
            return pool, feedback, [], {
                "enabled": False,
                "verified": False,
                "reason": "disabled_or_validator_unavailable",
            }

        max_repairs = max(
            0,
            int(os.getenv("HAILA_DISTRACTOR_QUALITY_MAX_REPAIRS", "3")),
        )
        repairs = 0
        checks = 0
        warnings: list[RedFlag] = []
        rejected_total = 0

        while True:
            if len(pool) < 4:
                pool, feedback = self._grow_pool(
                    request_id,
                    req,
                    nucleo,
                    distractor_generator,
                    feedback,
                    pool,
                )

            current = list(pool[:4])
            checks += 1
            rejections, provenance = validator(nucleo, current)
            payload = {
                "check": checks,
                "repair_cycle": repairs,
                "candidates": [d.to_dict() for d in current],
                "rejections": rejections,
            }
            self.repo.save_artifact(
                request_id,
                "DISTRACTOR_QUALITY_GATE",
                payload,
                provenance,
            )
            # Alias retained for old diagnostics/front-end readers.
            self.repo.save_artifact(
                request_id,
                "DISTRACTOR_SEMANTIC_GATE",
                payload,
                {**provenance, "compatibility_alias": True},
            )

            if not provenance.get("parse_ok", True):
                warnings = [
                    RedFlag(
                        "auditoria_qualidade_distratores_inconclusiva",
                        "DISTRATORES",
                        "alternativas",
                        "o auditor local não devolveu JSON interpretável; candidatos preservados para revisão humana",
                        "DISTRATORES",
                    )
                ]
                return pool, feedback, warnings, {
                    "enabled": True,
                    "verified": False,
                    "parse_ok": False,
                    "checks": checks,
                    "repairs": repairs,
                    "rejected_total": rejected_total,
                    "active_count": min(len(pool), 4),
                    "reserve_count": max(0, len(pool) - 4),
                }

            rejected_indices = {
                int(item.get("indice"))
                for item in rejections
                if isinstance(item, dict)
                and str(item.get("indice", "")).lstrip("-").isdigit()
                and 0 <= int(item.get("indice")) < len(current)
            }
            if not rejected_indices:
                for idx, candidato in enumerate(current):
                    self.repo.save_artifact(
                        request_id,
                        "DISTRACTOR_CANDIDATE_VALIDATED_QUALITY",
                        candidato.to_dict(),
                        {
                            "check": checks,
                            "index": idx,
                            "criteria": provenance.get("criterios", []),
                            "gate": provenance,
                        },
                    )
                return pool, feedback, [], {
                    "enabled": True,
                    "verified": True,
                    "parse_ok": True,
                    "checks": checks,
                    "repairs": repairs,
                    "rejected_total": rejected_total,
                    "active_count": 4,
                    "reserve_count": max(0, len(pool) - 4),
                }

            # Do not loop forever. If the local auditor still rejects candidates
            # after the repair budget, deliver the item with explicit warnings for
            # the professor rather than resetting the entire question.
            if repairs >= max_repairs:
                for item in rejections:
                    if not isinstance(item, dict):
                        continue
                    try:
                        idx = int(item.get("indice"))
                    except (TypeError, ValueError):
                        continue
                    if idx not in rejected_indices:
                        continue
                    candidato = current[idx]
                    code = str(item.get("codigo") or "qualidade_distrator")
                    motivo = str(item.get("motivo") or "distrator requer revisão humana")
                    warnings.append(
                        RedFlag(
                            f"distrator_{code}",
                            "DISTRATORES",
                            f"distratores[{idx}]",
                            f"{candidato.texto}: {motivo}"[:700],
                            "DISTRATORES",
                        )
                    )
                return pool, feedback, warnings, {
                    "enabled": True,
                    "verified": False,
                    "parse_ok": True,
                    "checks": checks,
                    "repairs": repairs,
                    "rejected_total": rejected_total + len(rejected_indices),
                    "active_count": 4,
                    "reserve_count": max(0, len(pool) - 4),
                    "reason": "repair_budget_exhausted_advisory_delivery",
                }

            round_feedback: list[dict[str, Any]] = []
            rejected_keys = set()
            for item in rejections:
                if not isinstance(item, dict):
                    continue
                try:
                    idx = int(item.get("indice"))
                except (TypeError, ValueError):
                    continue
                if idx not in rejected_indices:
                    continue
                candidato = current[idx]
                rejected_keys.add(_candidate_key(candidato.texto))
                code = str(item.get("codigo") or "implausivel")
                motivo = str(
                    item.get("motivo")
                    or "candidato não atende aos critérios de qualidade do distrator"
                )
                feedback_item = {
                    "codigo": f"distrator_{code}",
                    "etapa": "DISTRATORES",
                    "campo": f"distratores[{idx}]",
                    "evidencia": motivo[:700],
                    "reparo": "DISTRATORES",
                    "alternativa_rejeitada": candidato.texto,
                }
                round_feedback.append(feedback_item)
                self.repo.save_artifact(
                    request_id,
                    "DISTRACTOR_CANDIDATE_REJECTED_QUALITY",
                    candidato.to_dict(),
                    {
                        "check": checks,
                        "repair_cycle": repairs + 1,
                        "quality_code": code,
                        "reason": motivo[:700],
                        "gate": provenance,
                    },
                )
                # Compatibility with v2 diagnostics.
                if code in {"segunda_resposta", "equivalente_gabarito"}:
                    self.repo.save_artifact(
                        request_id,
                        "DISTRACTOR_CANDIDATE_REJECTED_SEMANTIC",
                        candidato.to_dict(),
                        {
                            "check": checks,
                            "semantic_code": code,
                            "reason": motivo[:700],
                            "gate": provenance,
                            "compatibility_alias": True,
                        },
                    )

            rejected_total += len(rejected_keys)
            repairs += 1
            active_before = list(pool[:4])
            reserves_before = list(pool[4:])
            reserve_keys_before = {_candidate_key(d.texto) for d in reserves_before}
            pool = [d for d in pool if _candidate_key(d.texto) not in rejected_keys]
            for promoted_index, candidato in enumerate(pool[:4]):
                if _candidate_key(candidato.texto) not in reserve_keys_before:
                    continue
                self.repo.save_artifact(
                    request_id,
                    "DISTRACTOR_RESERVE_PROMOTED",
                    candidato.to_dict(),
                    {
                        "check": checks,
                        "repair_cycle": repairs,
                        "promoted_to_index": promoted_index,
                        "reason": "quality_rejection_replacement",
                        "rejected_active_count": len(rejected_keys),
                        "active_before": [d.texto for d in active_before],
                    },
                )
            self.repo.save_distractor_pool(
                request_id,
                pool,
                {
                    "quality_gate_check": checks,
                    "repair_cycle": repairs,
                    "accepted_total": len(pool),
                    "active_count": min(len(pool), 4),
                    "reserve_count": max(0, len(pool) - 4),
                    "required": 4,
                    "quality_rejections": len(rejected_keys),
                },
            )
            feedback = round_feedback or feedback
            # The next loop promotes existing reserves automatically. Only when
            # fewer than four remain will _grow_pool call the local SLM again.

    def _select_four(self, nucleo, distractor_generator, pool):
        if len(pool) < 4:
            raise ValueError("pool persistente ainda não contém quatro candidatos")
        # Only the first four have passed the final quality gate. Reserves are
        # intentionally not eligible for final selection until promoted/audited.
        return list(pool[:4]), {
            "modelo": "quality_verified_active_pool",
            "indices_selecionados": [0, 1, 2, 3],
            "reserve_count": max(0, len(pool) - 4),
        }

    def _executar(
        self,
        request_id: str,
        rag,
        stem_generator,
        distractor_generator,
        red_flag_analyzer,
        jev_evaluator=None,
    ) -> dict:
        req = self.repo.get_request(request_id)
        current = Estado(req["state"])
        if current == Estado.GENERATION_COMPLETED:
            version = self.repo.latest_version(request_id)
            return {
                "request_id": request_id,
                "version": version,
                "state": Estado.GENERATION_COMPLETED.value,
                "red_flags": [],
                "resumed": True,
            }
        if current in {Estado.ATTEMPTS_EXHAUSTED, Estado.GENERATION_FAILED}:
            raise RuntimeError(
                "solicitação antiga já está em estado terminal; crie uma nova para usar o pipeline sustentável"
            )

        referencia = self._load_reference(request_id, req, rag)
        req = self.repo.get_request(request_id)
        nucleo, stem_warnings = self._load_or_generate_stem(
            request_id,
            req,
            referencia,
            stem_generator,
        )

        pool = self._load_pool(request_id)
        feedback: list[dict[str, Any]] = []
        pool, feedback = self._grow_pool(
            request_id,
            req,
            nucleo,
            distractor_generator,
            feedback,
            pool,
        )
        pool, feedback, quality_gate_warnings, quality_gate_summary = self._quality_gate_pool(
            request_id,
            req,
            nucleo,
            distractor_generator,
            pool,
            feedback,
        )

        selected, selection_prov = self._select_four(
            nucleo,
            distractor_generator,
            pool,
        )
        full_flags = avaliar_distratores(nucleo, selected)
        if full_flags:
            # Candidate-level validation should already have removed almost all
            # of these. We keep them visible and do not reset the whole question.
            payload = [f.to_dict() for f in full_flags]
            self.repo.record_flags(request_id, payload)
            self.repo.save_artifact(
                request_id,
                "DISTRACTOR_SET_QUALITY_FLAGS",
                payload,
                {"policy": "localized_no_full_reset"},
            )

        self.repo.save_artifact(
            request_id,
            "DISTRACTORS",
            [d.to_dict() for d in selected],
            {
                "modelo": getattr(distractor_generator, "model", "slm"),
                "modo_incremental": True,
                "candidate_bank_size": len(pool),
                "selection": selection_prov,
                "legacy_attempt_limit_used_as_terminal": False,
            },
        )
        self._transition_if_possible(
            request_id,
            None,
            Estado.DISTRACTORS_GENERATED,
            "HAILA_SLM",
            "quatro distratores válidos reunidos incrementalmente",
            {
                "candidate_bank_size": len(pool),
                "selected": 4,
            },
        )

        questao = montar_item(nucleo, selected, request_id)
        item_flags = avaliar_item(questao)
        if item_flags:
            payload = [f.to_dict() for f in item_flags]
            self.repo.record_flags(request_id, payload)
            raise RuntimeError(
                "montagem estrutural inválida: "
                + ", ".join(sorted({f.codigo for f in item_flags}))
            )

        version = self.repo.add_version(
            request_id,
            questao,
            {
                "rag_id": referencia.id,
                "llm": stem_generator.model,
                "slm": distractor_generator.model,
                "pipeline": "sustainable-quality-v3",
                "candidate_bank_size": len(pool),
            },
        )
        self._transition_if_possible(
            request_id,
            version["id"],
            Estado.ITEM_ASSEMBLED,
            "HAILA_ASSEMBLER",
            "item montado a partir de checkpoints",
            {"candidate_bank_size": len(pool)},
        )

        warnings: list[RedFlag] = (
            list(stem_warnings)
            + list(full_flags)
            + list(quality_gate_warnings)
        )
        deterministic_flags, deterministic_prov = red_flag_analyzer(
            questao,
            req["specification"],
            referencia.to_dict(),
        )
        self.repo.save_artifact(
            request_id,
            "DETERMINISTIC_RED_FLAGS",
            [f.to_dict() for f in deterministic_flags],
            {
                **deterministic_prov,
                "policy": "advisory_after_structural_validation",
            },
        )
        if deterministic_flags:
            payload = [f.to_dict() for f in deterministic_flags]
            self.repo.record_flags(request_id, payload)
            warnings.extend(deterministic_flags)

        jev_completed = False
        if jev_evaluator is not None:
            try:
                jev_result, jev_prov = jev_evaluator(
                    questao,
                    req["specification"],
                    referencia.to_dict(),
                )
                self.repo.save_artifact(
                    request_id,
                    "JEV_SEMANTIC_EVALUATION",
                    jev_result,
                    jev_prov,
                )
                jev_completed = True
                jev_flags = jev_evaluator.blocking_flags(jev_result)
                if jev_flags:
                    payload = [f.to_dict() for f in jev_flags]
                    self.repo.record_flags(request_id, payload)
                    warnings.extend(jev_flags)
            except Exception as exc:
                self.repo.save_artifact(
                    request_id,
                    "JEV_ERROR",
                    {
                        "type": type(exc).__name__,
                        "message": str(exc)[:800],
                    },
                    {
                        "provider": "typesafe",
                        "mode": getattr(jev_evaluator, "mode", "unknown"),
                    },
                )
                if getattr(jev_evaluator, "fail_policy", "continue") == "error":
                    raise

        warning_payload = [f.to_dict() for f in warnings]
        self.repo.save_artifact(
            request_id,
            "QUALITY_SUMMARY",
            {
                "warnings": warning_payload,
                "warning_count": len(warning_payload),
                "candidate_bank_size": len(pool),
                "stem_locked": True,
                "jev_completed": jev_completed,
                "distractor_quality_gate": quality_gate_summary,
                "active_distractors": min(len(pool), 4),
                "reserve_distractors": max(0, len(pool) - 4),
            },
            {
                "policy": "professor_final_decision",
                "full_regeneration_on_warning": False,
            },
        )

        self._transition_if_possible(
            request_id,
            version["id"],
            Estado.GENERATION_COMPLETED,
            "HAILA_QUALITY",
            (
                "geração concluída com alertas preservados para revisão humana"
                if warning_payload
                else "geração concluída sem alertas automáticos"
            ),
            {
                "warning_count": len(warning_payload),
                "candidate_bank_size": len(pool),
                "stem_reused": self.repo.latest_artifact(request_id, "STEM_CHECKPOINT") is not None,
            },
        )
        return {
            "request_id": request_id,
            "version": version,
            "state": Estado.GENERATION_COMPLETED.value,
            "red_flags": warning_payload,
            "quality_warnings": warning_payload,
            "candidate_bank_size": len(pool),
            "active_distractors": min(len(pool), 4),
            "reserve_distractors": max(0, len(pool) - 4),
            "distractor_quality_gate": quality_gate_summary,
            "stem_locked": True,
        }


def montar_item(
    nucleo: NucleoQuestao,
    distratores: list[DistratorGerado],
    seed: str,
) -> dict[str, Any]:
    itens = [(nucleo.resposta_correta, None)] + [
        (d.texto, i) for i, d in enumerate(distratores)
    ]
    rnd = random.Random(hashlib.sha256(seed.encode()).hexdigest())
    rnd.shuffle(itens)
    correta = next(i for i, (_, origem) in enumerate(itens) if origem is None)
    rastreio = [
        {"indice_final": i, "distrator_origem": origem}
        for i, (_, origem) in enumerate(itens)
        if origem is not None
    ]
    return {
        "exame": "ENADE",
        "enunciado": nucleo.enunciado,
        "alternativas": [x[0] for x in itens],
        "correta": correta,
        "explicacao": nucleo.explicacao,
        "competencia": nucleo.competencia,
        "habilidade": nucleo.habilidade,
        "objeto_conhecimento": nucleo.objeto_conhecimento,
        "tem_imagem": nucleo.tem_imagem,
        "recurso_visual": nucleo.recurso_visual,
        "rastreio_distratores": rastreio,
    }
