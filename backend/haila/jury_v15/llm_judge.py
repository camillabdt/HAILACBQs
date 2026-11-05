from __future__ import annotations

import json
import re
import time
from typing import Any

from .models import (
    JudgeConfig,
    JudgeFinding,
    JudgeReport,
    JudgeType,
    JuryProfile,
    QuestionPayload,
)
from .redflags import RedFlagRegistry


class JudgeOutputError(RuntimeError):
    pass


class RateLimitPauseError(RuntimeError):
    def __init__(
        self,
        retry_after_seconds: float,
        message: str,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = max(
            1.0,
            float(retry_after_seconds),
        )


def _is_rate_limit_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".casefold()
    return (
        "ratelimiterror" in text
        or "rate limit" in text
        or "rate_limit_exceeded" in text
        or "error code: 429" in text
    )


def _parse_retry_after_seconds(
    exc: Exception,
) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)

    if headers:
        value = headers.get("retry-after")
        if value is not None:
            try:
                return max(0.0, float(value))
            except (TypeError, ValueError):
                pass

    text = str(exc)

    milliseconds_match = re.search(
        r"Please try again in\s+"
        r"(?P<milliseconds>\d+(?:\.\d+)?)ms\b",
        text,
        flags=re.IGNORECASE,
    )
    if milliseconds_match:
        return (
            float(
                milliseconds_match.group(
                    "milliseconds"
                )
            )
            / 1000
        )

    duration_match = re.search(
        r"Please try again in\s+"
        r"(?:(?P<minutes>\d+(?:\.\d+)?)m)?"
        r"(?:(?P<seconds>\d+(?:\.\d+)?)s)?\b",
        text,
        flags=re.IGNORECASE,
    )

    if not duration_match:
        return None

    minutes = float(
        duration_match.group("minutes") or 0.0
    )
    seconds = float(
        duration_match.group("seconds") or 0.0
    )

    total = minutes * 60 + seconds
    return total if total > 0 else None


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()

    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")

        if start < 0 or end <= start:
            raise JudgeOutputError(
                "O juiz não retornou JSON."
            )

        value = json.loads(text[start : end + 1])

    if not isinstance(value, dict):
        raise JudgeOutputError(
            "O retorno do juiz não é um objeto JSON."
        )

    return value


def _is_gpt_oss_model(model: str | None) -> bool:
    return bool(
        model
        and model.startswith("openai/gpt-oss-")
    )


class GroqAreaJudge:
    @staticmethod
    def _resolve_specialty(
        judge: JudgeConfig,
        question: QuestionPayload,
    ) -> str:
        specialty = judge.specialty_area.strip()

        if specialty.casefold() in {
            "área da questão",
            "area da questao",
            "area_da_questao",
        }:
            return question.area

        return specialty

    @staticmethod
    def _strict_response_format(
        judge: JudgeConfig,
        profile: JuryProfile,
    ) -> dict[str, Any]:
        selected_ids = [
            selection.red_flag_id
            for selection in profile.red_flags
        ]

        finding_schema = {
            "type": "object",
            "properties": {
                "detected": {
                    "type": "boolean",
                },
                "severity": {
                    "type": "string",
                    "enum": [
                        "none",
                        "minor",
                        "major",
                        "critical",
                    ],
                },
                "confidence": {
                    "type": "number",
                },
                "evidence": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
                "recommendation": {
                    "type": "string",
                },
            },
            "required": [
                "detected",
                "severity",
                "confidence",
                "evidence",
                "recommendation",
            ],
            "additionalProperties": False,
        }

        findings_properties = {
            red_flag_id: finding_schema
            for red_flag_id in selected_ids
        }

        schema = {
            "type": "object",
            "properties": {
                "judge_id": {
                    "type": "string",
                    "enum": [judge.id],
                },
                "findings": {
                    "type": "object",
                    "properties": findings_properties,
                    "required": selected_ids,
                    "additionalProperties": False,
                },
            },
            "required": [
                "judge_id",
                "findings",
            ],
            "additionalProperties": False,
        }

        return {
            "type": "json_schema",
            "json_schema": {
                "name": "cbq_judge_report",
                "strict": True,
                "schema": schema,
            },
        }

    def __init__(
        self,
        api_key: str,
        max_attempts: int = 3,
        pause_seconds: float = 2.0,
        min_request_interval_seconds: float = 15.0,
        max_automatic_rate_wait_seconds: float = 60.0,
        rate_limit_safety_seconds: float = 3.0,
    ) -> None:
        try:
            from groq import Groq
        except ImportError as exc:
            raise RuntimeError(
                "Pacote groq não instalado. "
                "Execute: pip install groq"
            ) from exc

        self.client = Groq(
            api_key=api_key,
            max_retries=0,
            timeout=120,
        )
        self.max_attempts = max(1, max_attempts)
        self.pause_seconds = max(
            0.0,
            pause_seconds,
        )
        self.min_request_interval_seconds = max(
            0.0,
            min_request_interval_seconds,
        )
        self.max_automatic_rate_wait_seconds = max(
            0.0,
            max_automatic_rate_wait_seconds,
        )
        self.rate_limit_safety_seconds = max(
            0.0,
            rate_limit_safety_seconds,
        )
        self._last_request_started_at: (
            float | None
        ) = None

    def _wait_for_request_slot(self) -> None:
        if self._last_request_started_at is None:
            self._last_request_started_at = (
                time.monotonic()
            )
            return

        elapsed = (
            time.monotonic()
            - self._last_request_started_at
        )
        remaining = (
            self.min_request_interval_seconds
            - elapsed
        )

        if remaining > 0:
            time.sleep(remaining)

        self._last_request_started_at = (
            time.monotonic()
        )

    def _selected_redflags(
        self,
        profile: JuryProfile,
        registry: RedFlagRegistry,
    ) -> list[dict[str, str]]:
        selected: list[dict[str, str]] = []

        for selection in profile.red_flags:
            definition = registry.get(
                selection.red_flag_id
            )
            selected.append(
                {
                    "id": definition.id,
                    "name": definition.name,
                    "description": (
                        definition.description
                    ),
                    "instruction": (
                        definition.prompt_instruction
                    ),
                }
            )

        return selected

    def _messages(
        self,
        judge: JudgeConfig,
        profile: JuryProfile,
        question: QuestionPayload,
        registry: RedFlagRegistry,
        previous_error: str | None,
    ) -> list[dict[str, str]]:
        specialty = self._resolve_specialty(
            judge,
            question,
        )
        selected = self._selected_redflags(
            profile,
            registry,
        )

        system = (
            "Você é um juiz especializado em "
            f"{specialty}. Analise todas as Red Flags "
            "fornecidas, uma por uma. Não faça votação "
            "geral e não decida aprovação global. O campo "
            "findings é um objeto obrigatório com uma chave "
            "para cada ID recebido em required_ids. Nenhuma "
            "chave pode ser omitida. Para cada flag, informe "
            "detecção, gravidade, confiança, evidências "
            "objetivas e recomendação. Seja breve: no máximo "
            "duas evidências curtas por flag. Uma flag não "
            "detectada deve usar severity=none, evidence=[] "
            "e recommendation=''."
        )

        payload: dict[str, Any] = {
            "question": {
                "area": question.area,
                "year": question.year,
                "context": question.context,
                "statement": question.statement,
                "answer_key": question.answer_key,
                "distractors": question.distractors,
            },
            "red_flags": selected,
            "judge_id": judge.id,
            "required_ids": [
                item["id"]
                for item in selected
            ],
        }

        if previous_error:
            payload["previous_error"] = previous_error

        return [
            {
                "role": "system",
                "content": system,
            },
            {
                "role": "user",
                "content": json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ]

    def _request_options(
        self,
        judge: JudgeConfig,
        profile: JuryProfile,
    ) -> dict[str, Any]:
        if _is_gpt_oss_model(judge.model):
            return {
                "temperature": 0,
                "max_completion_tokens": 1100,
                "include_reasoning": False,
                "reasoning_effort": "low",
                "response_format": (
                    self._strict_response_format(
                        judge,
                        profile,
                    )
                ),
            }

        return {
            "temperature": 0,
            "max_completion_tokens": 900,
            "response_format": {
                "type": "json_object",
            },
        }

    def _validate(
        self,
        raw: str,
        judge: JudgeConfig,
        profile: JuryProfile,
        question: QuestionPayload,
    ) -> JudgeReport:
        data = _extract_json(raw)

        raw_findings = data.get("findings")
        expected_ids = [
            selection.red_flag_id
            for selection in profile.red_flags
        ]

        if isinstance(raw_findings, dict):
            normalized_items = [
                {
                    "red_flag_id": red_flag_id,
                    **raw_findings[red_flag_id],
                }
                for red_flag_id in expected_ids
                if red_flag_id in raw_findings
            ]
        elif isinstance(raw_findings, list):
            normalized_items = raw_findings
        else:
            raise JudgeOutputError(
                "Campo findings ausente ou inválido."
            )

        findings = [
            JudgeFinding.model_validate(item)
            for item in normalized_items
        ]
        received_ids = [
            finding.red_flag_id
            for finding in findings
        ]

        if sorted(received_ids) != sorted(
            expected_ids
        ):
            raise JudgeOutputError(
                "Red Flags incompletas. "
                f"Esperado {expected_ids}; "
                f"recebido {received_ids}."
            )

        if len(received_ids) != len(
            set(received_ids)
        ):
            raise JudgeOutputError(
                "Red Flags duplicadas no relatório."
            )

        return JudgeReport(
            judge_id=judge.id,
            judge_type=JudgeType.LLM,
            specialty_area=(
                self._resolve_specialty(
                    judge,
                    question,
                )
            ),
            model=judge.model,
            status="completed",
            findings=findings,
            raw_output=raw,
        )

    def evaluate(
        self,
        judge: JudgeConfig,
        profile: JuryProfile,
        question: QuestionPayload,
        registry: RedFlagRegistry,
    ) -> JudgeReport:
        previous_error: str | None = None
        last_error: Exception | None = None
        started = time.perf_counter()
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0
        api_attempts = 0

        for attempt in range(
            1,
            self.max_attempts + 1,
        ):
            try:
                self._wait_for_request_slot()
                api_attempts += 1

                response = (
                    self.client
                    .chat
                    .completions
                    .create(
                        model=judge.model,
                        messages=self._messages(
                            judge,
                            profile,
                            question,
                            registry,
                            previous_error,
                        ),
                        **self._request_options(
                            judge,
                            profile,
                        ),
                    )
                )

                usage = getattr(response, "usage", None)
                if usage is not None:
                    total_input_tokens += int(
                        getattr(usage, "prompt_tokens", 0) or 0
                    )
                    total_output_tokens += int(
                        getattr(usage, "completion_tokens", 0) or 0
                    )
                    total_tokens += int(
                        getattr(usage, "total_tokens", 0) or 0
                    )

                raw = (
                    response
                    .choices[0]
                    .message
                    .content
                    or ""
                )

                report = self._validate(
                    raw,
                    judge,
                    profile,
                    question,
                )
                report.input_tokens = total_input_tokens
                report.output_tokens = total_output_tokens
                report.total_tokens = (
                    total_tokens
                    or total_input_tokens + total_output_tokens
                )
                report.latency_ms = round(
                    (time.perf_counter() - started) * 1000,
                    3,
                )
                report.api_attempts = api_attempts
                return report

            except Exception as exc:
                last_error = exc
                previous_error = (
                    f"{type(exc).__name__}: {exc}"
                )

                if _is_rate_limit_error(exc):
                    retry_after = (
                        _parse_retry_after_seconds(
                            exc
                        )
                        or 60.0
                    )
                    retry_after += (
                        self.rate_limit_safety_seconds
                    )

                    if (
                        retry_after
                        > self
                        .max_automatic_rate_wait_seconds
                    ):
                        raise RateLimitPauseError(
                            retry_after,
                            previous_error,
                        ) from exc

                    if attempt < self.max_attempts:
                        time.sleep(retry_after)
                        continue

                    raise RateLimitPauseError(
                        retry_after,
                        previous_error,
                    ) from exc

                if attempt < self.max_attempts:
                    time.sleep(
                        self.pause_seconds * attempt
                    )

        return JudgeReport(
            judge_id=judge.id,
            judge_type=JudgeType.LLM,
            specialty_area=(
                self._resolve_specialty(
                    judge,
                    question,
                )
            ),
            model=judge.model,
            status="error",
            findings=[],
            error=(
                "Falha após "
                f"{self.max_attempts} tentativas: "
                f"{type(last_error).__name__}: "
                f"{last_error}"
            ),
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            total_tokens=(
                total_tokens
                or total_input_tokens + total_output_tokens
            ),
            latency_ms=round(
                (time.perf_counter() - started) * 1000,
                3,
            ),
            api_attempts=api_attempts,
        )
