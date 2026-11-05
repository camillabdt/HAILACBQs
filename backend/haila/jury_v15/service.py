from __future__ import annotations

from pathlib import Path

from .aggregator import aggregate_record
from .jury import JuryProfileService
from .llm_judge import (
    GroqAreaJudge,
    RateLimitPauseError,
)
from .models import (
    EvaluationRecord,
    HumanReportRequest,
    JudgeReport,
    JudgeType,
    QuestionPayload,
)
from .redflags import RedFlagRegistry
from .repository import JsonObjectRepository


class EvaluationService:
    def __init__(
        self,
        evaluations_path: Path,
        profiles: JuryProfileService,
        registry: RedFlagRegistry,
        llm_judge: GroqAreaJudge | None,
    ) -> None:
        self.repository = JsonObjectRepository(
            evaluations_path,
            EvaluationRecord,
        )
        self.profiles = profiles
        self.registry = registry
        self.llm_judge = llm_judge

    def run(
        self,
        profile_id: str,
        question: QuestionPayload,
        metadata: dict | None = None,
        existing_record: EvaluationRecord | None = None,
    ) -> EvaluationRecord:
        profile = self.profiles.get(profile_id)

        reusable_reports = []
        can_reuse = (
            existing_record is not None
            and existing_record.profile_snapshot
            .model_dump(mode="json")
            == profile.model_dump(mode="json")
        )
        if can_reuse:
            reusable_reports = [
                report
                for report in existing_record.reports
                if report.status == "completed"
            ]

        merged_metadata = {
            **(
                existing_record.metadata
                if existing_record is not None
                else {}
            ),
            **(metadata or {}),
        }
        merged_metadata.pop(
            "rate_limit_pause",
            None,
        )

        record_data = {
            "profile_id": profile.id,
            "profile_snapshot": profile,
            "question": question,
            "reports": reusable_reports,
            "metadata": merged_metadata,
        }
        if existing_record is not None:
            record_data["id"] = existing_record.id
            record_data["created_at"] = (
                existing_record.created_at
            )

        record = EvaluationRecord(**record_data)

        completed_ids = {
            report.judge_id
            for report in record.reports
            if report.status == "completed"
        }

        for judge in profile.judges:
            if not judge.enabled or judge.type != JudgeType.LLM:
                continue
            if judge.id in completed_ids:
                continue

            if self.llm_judge is None:
                record.reports.append(
                    JudgeReport(
                        judge_id=judge.id,
                        judge_type=JudgeType.LLM,
                        specialty_area=judge.specialty_area,
                        model=judge.model,
                        status="error",
                        error="GROQ_API_KEY não configurada.",
                    )
                )
                continue

            try:
                report = self.llm_judge.evaluate(
                    judge,
                    profile,
                    question,
                    self.registry,
                )
                record.reports.append(report)
            except RateLimitPauseError as exc:
                record.reports.append(
                    JudgeReport(
                        judge_id=judge.id,
                        judge_type=JudgeType.LLM,
                        specialty_area=judge.specialty_area,
                        model=judge.model,
                        status="error",
                        error=(
                            "RATE_LIMIT_PAUSE: "
                            f"{exc}"
                        ),
                        retry_after_seconds=(
                            exc.retry_after_seconds
                        ),
                    )
                )
                record.metadata["rate_limit_pause"] = {
                    "judge_id": judge.id,
                    "retry_after_seconds": (
                        exc.retry_after_seconds
                    ),
                }
                break

        record = aggregate_record(record, self.registry)
        return self.repository.upsert(record)

    def get(self, evaluation_id: str) -> EvaluationRecord:
        return self.repository.get(evaluation_id)

    def add_human_report(
        self,
        evaluation_id: str,
        payload: HumanReportRequest,
    ) -> EvaluationRecord:
        record = self.repository.get(evaluation_id)
        configured = {
            judge.id: judge
            for judge in record.profile_snapshot.judges
            if judge.enabled and judge.type == JudgeType.HUMAN
        }

        report = payload.report
        if report.judge_id not in configured:
            raise ValueError(
                f"Juiz humano não pertence ao perfil: {report.judge_id}"
            )

        record.reports = [
            current
            for current in record.reports
            if current.judge_id != report.judge_id
        ]
        record.reports.append(report)
        record = aggregate_record(record, self.registry)
        return self.repository.upsert(record)
