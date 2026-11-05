from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from .contracts import RedFlag

DEFAULT_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"

CRITERIA = {
    "gabarito_unico": {
        "instructions": (
            "Considerando enunciado, alternativas, gabarito e explicacao, "
            "existe exatamente uma alternativa defensavel como correta?"
        ),
        "true": "Ha exatamente uma alternativa defensavel como correta.",
        "false": (
            "Ha mais de uma alternativa defensavel, nenhuma correta, "
            "ou o gabarito indicado e inadequado."
        ),
        "repair": "NUCLEO",
    },
    "enunciado_claro": {
        "instructions": (
            "O enunciado contem contexto suficiente e um comando claro, "
            "sem depender de informacao essencial ausente?"
        ),
        "true": "O estudante entende precisamente o que deve responder.",
        "false": (
            "O comando e vago, incompleto, contraditorio ou depende "
            "de informacao essencial ausente."
        ),
        "repair": "NUCLEO",
    },
    "alinhamento_pedagogico": {
        "instructions": (
            "A questao avalia diretamente o objetivo pedagogico, a habilidade "
            "e o objeto de conhecimento informados na especificacao?"
        ),
        "true": "O conteudo cobrado esta alinhado a especificacao pedagogica.",
        "false": "O item cobra outro conceito, outra habilidade ou desloca o foco.",
        "repair": "NUCLEO",
    },
    "distratores_plausiveis": {
        "instructions": (
            "As quatro alternativas incorretas sao plausiveis para um estudante, "
            "pertencem ao mesmo nivel conceitual do gabarito e permanecem incorretas?"
        ),
        "true": "Os quatro distratores sao plausiveis, homogeneos e incorretos.",
        "false": (
            "Ha distrator absurdo, fora de categoria, quase correto, "
            "semanticamente duplicado ou pouco plausivel."
        ),
        "repair": "DISTRATORES",
    },
    "sem_ambiguidade": {
        "instructions": (
            "A questao pode ser respondida de modo nao ambiguo usando somente "
            "o enunciado, as alternativas e o conhecimento conceitual esperado?"
        ),
        "true": "A interpretacao e a resposta correta sao suficientemente nao ambiguas.",
        "false": (
            "Ha ambiguidade material, multiplas leituras defensaveis "
            "ou premissas incompativeis."
        ),
        "repair": "NUCLEO",
    },
}


class JevEvaluationError(RuntimeError):
    pass


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on", "sim"}


def _optional_float(name: str) -> float | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    value = float(raw)
    if not 0 <= value <= 1:
        raise RuntimeError(f"{name} deve estar entre 0 e 1")
    return value


def jev_runtime_status() -> dict[str, Any]:
    return {
        "enabled": _env_bool("HAILA_JEV_ENABLED", False),
        "configured": bool(os.getenv("TYPESAFE_API_KEY", "").strip()),
        "mode": os.getenv("HAILA_JEV_MODE", "shadow").strip().casefold(),
        "model": os.getenv("HAILA_JEV_MODEL", DEFAULT_MODEL),
        "endpoint": os.getenv("HAILA_JEV_ENDPOINT", DEFAULT_ENDPOINT),
        "pass_threshold_configured": bool(
            os.getenv("HAILA_JEV_PASS_THRESHOLD", "").strip()
        ),
        "review_threshold_configured": bool(
            os.getenv("HAILA_JEV_REVIEW_THRESHOLD", "").strip()
        ),
        "fail_policy": os.getenv(
            "HAILA_JEV_FAIL_POLICY", "continue"
        ).strip().casefold(),
    }


class JevSemanticEvaluator:
    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str = DEFAULT_ENDPOINT,
        model: str = DEFAULT_MODEL,
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        mode: str = "shadow",
        pass_threshold: float | None = None,
        review_threshold: float | None = None,
        fail_policy: str = "continue",
        input_price_per_million: float | None = None,
        transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ):
        self.api_key = api_key.strip()
        self.endpoint = endpoint.strip()
        self.model = model.strip()
        self.timeout_seconds = float(timeout_seconds)
        self.max_retries = int(max_retries)
        self.mode = mode.strip().casefold()
        self.pass_threshold = pass_threshold
        self.review_threshold = review_threshold
        self.fail_policy = fail_policy.strip().casefold()
        self.input_price_per_million = input_price_per_million
        self.transport = transport

        if not self.api_key and transport is None:
            raise RuntimeError("TYPESAFE_API_KEY nao configurada")
        if self.mode not in {"shadow", "gate"}:
            raise RuntimeError("HAILA_JEV_MODE deve ser shadow ou gate")
        if self.fail_policy not in {"continue", "error"}:
            raise RuntimeError("HAILA_JEV_FAIL_POLICY deve ser continue ou error")
        if self.mode == "gate" and self.pass_threshold is None:
            raise RuntimeError(
                "HAILA_JEV_MODE=gate exige HAILA_JEV_PASS_THRESHOLD explicito"
            )
        if (
            self.review_threshold is not None
            and self.pass_threshold is not None
            and self.review_threshold > self.pass_threshold
        ):
            raise RuntimeError(
                "HAILA_JEV_REVIEW_THRESHOLD deve ser <= HAILA_JEV_PASS_THRESHOLD"
            )

    def _decision(self, probability: float) -> str:
        if self.pass_threshold is None:
            return "OBSERVE"
        if probability >= self.pass_threshold:
            return "PASS"
        if (
            self.review_threshold is not None
            and probability >= self.review_threshold
        ):
            return "REVIEW"
        return "FAIL"

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.transport is not None:
            return self.transport(payload)

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        for attempt in range(self.max_retries + 1):
            request = urllib.request.Request(
                self.endpoint, data=body, headers=headers, method="POST"
            )
            try:
                with urllib.request.urlopen(
                    request, timeout=self.timeout_seconds
                ) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                if exc.code in {429, 529} and attempt < self.max_retries:
                    retry_after = exc.headers.get("Retry-After")
                    try:
                        wait = float(retry_after)
                    except Exception:
                        wait = min(8.0, 0.75 * (2 ** attempt))
                    time.sleep(max(0.25, wait))
                    continue
                raise JevEvaluationError(
                    f"TypeSafe Jev HTTP {exc.code}: {detail[:600]}"
                ) from exc
            except urllib.error.URLError as exc:
                if attempt < self.max_retries:
                    time.sleep(min(8.0, 0.75 * (2 ** attempt)))
                    continue
                raise JevEvaluationError(
                    f"falha de comunicacao com TypeSafe Jev: {exc}"
                ) from exc

        raise JevEvaluationError("TypeSafe Jev falhou sem resposta")

    def __call__(
        self,
        question: dict[str, Any],
        specification: dict[str, Any],
        reference: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        alternatives = question.get("alternativas") or []
        correct = question.get("correta")
        answer_text = (
            alternatives[correct]
            if isinstance(correct, int) and 0 <= correct < len(alternatives)
            else None
        )

        state = {
            "specification": {
                key: specification.get(key)
                for key in (
                    "objetivo_pedagogico",
                    "competencia",
                    "habilidade",
                    "objeto_conhecimento",
                    "dificuldade",
                )
            },
            "reference": {
                "id": reference.get("id"),
                "texto": str(reference.get("texto") or "")[:12000],
            },
            "question": {
                "enunciado": question.get("enunciado"),
                "alternativas": alternatives,
                "correta": correct,
                "gabarito_texto": answer_text,
                "explicacao": question.get("explicacao"),
            },
        }

        questions = {
            key: {
                "type": "noul",
                "instructions": meta["instructions"],
                "criteria": {
                    "true": meta["true"],
                    "false": meta["false"],
                },
            }
            for key, meta in CRITERIA.items()
        }

        started = time.perf_counter()
        raw = self._post(
            {"model": self.model, "state": state, "questions": questions}
        )
        latency_ms = round((time.perf_counter() - started) * 1000, 2)

        answers = raw.get("answers")
        if not isinstance(answers, dict):
            raise JevEvaluationError("resposta Jev sem objeto answers")

        criteria = {}
        missing = []

        for key, meta in CRITERIA.items():
            answer = answers.get(key)
            if not isinstance(answer, dict) or "noul" not in answer:
                missing.append(key)
                continue
            probability = float(answer["noul"])
            if not 0 <= probability <= 1:
                raise JevEvaluationError(
                    f"noul fora de [0,1] em {key}: {probability}"
                )
            criteria[key] = {
                "probability_yes": probability,
                "decision": self._decision(probability),
                "repair_target": meta["repair"],
            }

        if missing:
            raise JevEvaluationError(
                "criterios ausentes: " + ", ".join(missing)
            )

        probabilities = [
            item["probability_yes"] for item in criteria.values()
        ]
        usage = raw.get("usage") or {}
        input_tokens = int(usage.get("input_tokens") or 0)

        estimated_cost_usd = None
        if self.input_price_per_million is not None:
            estimated_cost_usd = (
                input_tokens
                / 1_000_000
                * self.input_price_per_million
            )

        minimum_probability = min(probabilities)
        lowest_criterion = min(
            criteria,
            key=lambda key: criteria[key]["probability_yes"],
        )

        if self.mode == "shadow":
            requires_human_review = None
        else:
            requires_human_review = any(
                item["decision"] in {"REVIEW", "FAIL"}
                for item in criteria.values()
            )

        result = {
            "judge": "typesafe-jev",
            "mode": self.mode,
            "criteria": criteria,
            "minimum_probability": minimum_probability,
            "mean_probability": sum(probabilities) / len(probabilities),
            "lowest_criterion": lowest_criterion,
            "requires_human_review": requires_human_review,
            "blocking_failures": [
                key
                for key, item in criteria.items()
                if item["decision"] == "FAIL"
            ],
        }

        provenance = {
            "provider": "typesafe",
            "model_requested": self.model,
            "model_resolved": raw.get("model"),
            "endpoint": self.endpoint,
            "latency_ms": latency_ms,
            "mode": self.mode,
            "usage": usage,
            "input_price_per_million_usd": self.input_price_per_million,
            "estimated_cost_usd": estimated_cost_usd,
            "question_types": {key: "noul" for key in CRITERIA},
        }

        return result, provenance

    def blocking_flags(
        self,
        result: dict[str, Any],
    ) -> list[RedFlag]:
        if self.mode != "gate":
            return []

        flags = []
        for key, data in (result.get("criteria") or {}).items():
            if data.get("decision") != "FAIL":
                continue
            flags.append(
                RedFlag(
                    codigo=f"jev_{key}",
                    etapa="JEV",
                    campo=key,
                    evidencia=(
                        "Jev P(sim)="
                        f"{float(data.get('probability_yes', 0.0)):.4f}; "
                        f"limiar_pass={self.pass_threshold}; "
                        f"limiar_review={self.review_threshold}"
                    ),
                    reparo=str(data.get("repair_target") or "NUCLEO"),
                )
            )
        return flags


def jev_evaluator_from_env() -> JevSemanticEvaluator | None:
    if not _env_bool("HAILA_JEV_ENABLED", False):
        return None

    price_raw = os.getenv(
        "HAILA_JEV_INPUT_PRICE_PER_MILLION", ""
    ).strip()
    price = float(price_raw) if price_raw else None

    return JevSemanticEvaluator(
        api_key=os.getenv("TYPESAFE_API_KEY", ""),
        endpoint=os.getenv("HAILA_JEV_ENDPOINT", DEFAULT_ENDPOINT),
        model=os.getenv("HAILA_JEV_MODEL", DEFAULT_MODEL),
        timeout_seconds=float(
            os.getenv("HAILA_JEV_TIMEOUT_SECONDS", "20")
        ),
        max_retries=int(os.getenv("HAILA_JEV_MAX_RETRIES", "2")),
        mode=os.getenv("HAILA_JEV_MODE", "shadow"),
        pass_threshold=_optional_float("HAILA_JEV_PASS_THRESHOLD"),
        review_threshold=_optional_float(
            "HAILA_JEV_REVIEW_THRESHOLD"
        ),
        fail_policy=os.getenv("HAILA_JEV_FAIL_POLICY", "continue"),
        input_price_per_million=price,
    )
