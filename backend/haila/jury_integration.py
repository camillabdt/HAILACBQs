from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from .jury_v15.jury import JuryProfileService
from .jury_v15.llm_judge import GroqAreaJudge
from .jury_v15.models import (
    EvaluationStatus,
    JuryProfile,
    QuestionPayload,
)
from .jury_v15.redflags import RedFlagRegistry
from .jury_v15.service import EvaluationService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
JURY_DATA_DIR = PROJECT_ROOT / "runtime" / "jury"
PROFILE_ID = "haila-jury-llm-100-v1"
INTEGRATION_VERSION = "haila-jury-optional-20261020-v1"


def _enabled() -> bool:
    return os.getenv("HAILA_JURY_ENABLED", "1").strip().lower() not in {
        "0", "false", "no", "off",
    }


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _models() -> tuple[str, str]:
    return (
        os.getenv("HAILA_JURY_AREA_MODEL", "openai/gpt-oss-120b").strip(),
        os.getenv("HAILA_JURY_PEDAGOGICAL_MODEL", "openai/gpt-oss-20b").strip(),
    )


def _build_profile() -> JuryProfile:
    area_model, pedagogical_model = _models()
    selections = []
    for number in range(1, 9):
        item: dict[str, Any] = {"red_flag_id": f"RF{number}"}
        # RF1 (gabarito) e RF3 (contradição) só são consideradas
        # bloqueantes quando os dois juízes concordam. Uma divergência
        # crítica fica registrada e a recomendação agregada não aprova.
        if number in {1, 3}:
            item["threshold"] = 1.0
        else:
            item["threshold"] = 0.5
        selections.append(item)

    return JuryProfile(
        id=PROFILE_ID,
        name="HAILA — júri LLM opcional",
        question_area="Computação",
        red_flags=selections,
        judges=[
            {
                "id": "llm-area-01",
                "type": "llm",
                "display_name": "Juiz de conteúdo",
                "specialty_area": "área da questão",
                "model": area_model,
            },
            {
                "id": "llm-pedagogico-01",
                "type": "llm",
                "display_name": "Juiz pedagógico",
                "specialty_area": "pedagogia e avaliação educacional",
                "model": pedagogical_model,
            },
        ],
        group_weights={"llm": 100, "human": 0},
        default_detection_threshold=0.5,
        require_complete_jury=True,
        created_by="HAILA",
        active=True,
    )


def _services() -> tuple[JuryProfileService, EvaluationService, JuryProfile]:
    JURY_DATA_DIR.mkdir(parents=True, exist_ok=True)
    registry = RedFlagRegistry(JURY_DATA_DIR / "redflags_custom.json")
    profiles = JuryProfileService(JURY_DATA_DIR / "jury_profiles.json", registry)
    profile = _build_profile()
    profiles.create(profile)  # upsert: mantém snapshot reprodutível do perfil atual.

    key = os.getenv("GROQ_API_KEY", "").strip()
    llm_judge = None
    if key:
        llm_judge = GroqAreaJudge(
            api_key=key,
            max_attempts=int(os.getenv("HAILA_JURY_MAX_ATTEMPTS", "3")),
            pause_seconds=_float_env("HAILA_JURY_RETRY_PAUSE_SECONDS", 2.0),
            min_request_interval_seconds=_float_env(
                "HAILA_JURY_MIN_CALL_INTERVAL_SECONDS", 15.0
            ),
            max_automatic_rate_wait_seconds=_float_env(
                "HAILA_JURY_MAX_AUTOMATIC_RATE_WAIT_SECONDS", 60.0
            ),
            rate_limit_safety_seconds=_float_env(
                "HAILA_JURY_RATE_LIMIT_SAFETY_SECONDS", 3.0
            ),
        )

    evaluations = EvaluationService(
        JURY_DATA_DIR / "evaluations.json",
        profiles,
        registry,
        llm_judge,
    )
    return profiles, evaluations, profile


def jury_runtime_status() -> dict[str, Any]:
    area_model, pedagogical_model = _models()
    return {
        "enabled": _enabled(),
        "configured": bool(os.getenv("GROQ_API_KEY", "").strip()),
        "mode": "on_demand",
        "profile_id": PROFILE_ID,
        "area_model": area_model,
        "pedagogical_model": pedagogical_model,
        "human_in_jury": False,
        "human_decision": "independent_front_review",
        "auto_run_during_generation": False,
        "integration_version": INTEGRATION_VERSION,
    }


def build_question_payload_from_haila(
    request_id: str,
    version: dict[str, Any],
    request: dict[str, Any],
    history: dict[str, Any],
) -> QuestionPayload:
    question = version.get("question") or {}
    alternatives = [str(item) for item in (question.get("alternativas") or [])]
    correct_index = question.get("correta")
    if not isinstance(correct_index, int) or not (0 <= correct_index < len(alternatives)):
        raise ValueError("A questão não possui índice de gabarito válido.")

    reference = None
    for artifact in reversed(history.get("artifacts") or []):
        if artifact.get("kind") == "REFERENCE":
            reference = artifact.get("payload") or {}
            break
    reference = reference or {}

    specification = request.get("specification") or {}
    area = (
        question.get("objeto_conhecimento")
        or specification.get("objeto_conhecimento")
        or specification.get("curso")
        or "Computação"
    )

    return QuestionPayload(
        uid=f"{request_id}:{version.get('id', '')}",
        area=str(area),
        year=reference.get("ano"),
        context=str(reference.get("texto") or ""),
        statement=str(question.get("enunciado") or ""),
        answer_key=alternatives[correct_index],
        distractors=[
            text for index, text in enumerate(alternatives) if index != correct_index
        ],
    )


def _latest_success_artifact(history: dict[str, Any], version_id: str) -> dict[str, Any] | None:
    for artifact in reversed(history.get("artifacts") or []):
        if artifact.get("kind") != "JURY_LLM_EVALUATION":
            continue
        payload = artifact.get("payload") or {}
        if payload.get("version_id") == version_id:
            return artifact
    return None


def _existing_record(service: EvaluationService, version_id: str, profile: JuryProfile):
    for record in reversed(service.repository.list()):
        if (
            record.metadata.get("version_id") == version_id
            and record.profile_snapshot.model_dump(mode="json")
            == profile.model_dump(mode="json")
        ):
            return record
    return None


def _summary(record) -> dict[str, Any]:
    reports = [report for report in record.reports if report.status == "completed"]
    total_input = sum(report.input_tokens for report in reports)
    total_output = sum(report.output_tokens for report in reports)
    total_tokens = sum(report.total_tokens for report in reports)
    total_latency_ms = sum(report.latency_ms for report in reports)

    by_id = {report.judge_id: report for report in reports}
    agreement_pairs = 0
    agreements = 0
    disagreements: list[str] = []
    if len(by_id) >= 2:
        ordered = list(by_id.values())[:2]
        left = {item.red_flag_id: item.detected for item in ordered[0].findings}
        right = {item.red_flag_id: item.detected for item in ordered[1].findings}
        for red_flag_id in sorted(set(left) & set(right)):
            agreement_pairs += 1
            if left[red_flag_id] == right[red_flag_id]:
                agreements += 1
            else:
                disagreements.append(red_flag_id)

    return {
        "reports_completed": len(reports),
        "input_tokens": total_input,
        "output_tokens": total_output,
        "total_tokens": total_tokens,
        "judge_latency_ms_sum": round(total_latency_ms, 3),
        "agreement_rate": (
            round(agreements / agreement_pairs, 6) if agreement_pairs else None
        ),
        "disagreements": disagreements,
        "detected_flags": [
            item.red_flag_id for item in record.aggregated_flags if item.detected
        ],
        "disputed_flags": [
            item.red_flag_id for item in record.aggregated_flags if item.disputed
        ],
    }


def run_optional_jury(repo, request_id: str, force: bool = False) -> dict[str, Any]:
    if not _enabled():
        raise RuntimeError("Júri LLM desativado. Defina HAILA_JURY_ENABLED=1.")
    if not os.getenv("GROQ_API_KEY", "").strip():
        raise RuntimeError("GROQ_API_KEY não configurada para o júri LLM.")

    request = repo.get_request(request_id)
    if request.get("state") != "GENERATION_COMPLETED":
        raise ValueError("O júri só pode avaliar uma questão com geração concluída.")

    version = repo.latest_version(request_id)
    history = repo.history(request_id)

    if not force:
        cached = _latest_success_artifact(history, version["id"])
        if cached is not None:
            payload = cached.get("payload") or {}
            return {**payload, "cached": True}

    _, service, profile = _services()
    question = build_question_payload_from_haila(
        request_id=request_id,
        version=version,
        request=request,
        history=history,
    )
    existing = _existing_record(service, version["id"], profile)

    started = time.perf_counter()
    record = service.run(
        profile.id,
        question,
        metadata={
            "request_id": request_id,
            "version_id": version["id"],
            "integration_version": INTEGRATION_VERSION,
            "invocation": "professor_on_demand",
        },
        existing_record=existing,
    )
    wall_latency_ms = round((time.perf_counter() - started) * 1000, 3)

    if record.status == EvaluationStatus.PROCESS_ERROR:
        error_payload = {
            "request_id": request_id,
            "version_id": version["id"],
            "evaluation_id": record.id,
            "status": record.status.value,
            "process_errors": record.process_errors,
            "metadata": record.metadata,
            "wall_latency_ms": wall_latency_ms,
        }
        repo.save_artifact(
            request_id,
            "JURY_LLM_ERROR",
            error_payload,
            {
                "component": "HAILA_JURY",
                "mode": "on_demand",
                "profile_id": profile.id,
                "integration_version": INTEGRATION_VERSION,
            },
        )
        pause = record.metadata.get("rate_limit_pause") or {}
        retry_after = pause.get("retry_after_seconds")
        if retry_after:
            raise RuntimeError(
                "Limite temporário do provedor durante o júri. "
                f"Tente novamente após aproximadamente {float(retry_after):.0f} s."
            )
        raise RuntimeError(
            "O júri não concluiu a avaliação: " + "; ".join(record.process_errors)
        )

    evaluation = record.model_dump(mode="json")
    summary = _summary(record)
    payload = {
        "request_id": request_id,
        "version_id": version["id"],
        "evaluation_id": record.id,
        "cached": False,
        "wall_latency_ms": wall_latency_ms,
        "summary": summary,
        "evaluation": evaluation,
    }
    repo.save_artifact(
        request_id,
        "JURY_LLM_EVALUATION",
        payload,
        {
            "component": "HAILA_JURY",
            "mode": "on_demand",
            "profile_id": profile.id,
            "models": [judge.model for judge in profile.judges if judge.enabled],
            "integration_version": INTEGRATION_VERSION,
        },
    )
    return payload
