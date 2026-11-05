from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from .models import (
    AggregatedRedFlag,
    EvaluationRecord,
    EvaluationStatus,
    FinalAction,
    JudgeReport,
    JudgeType,
    JuryProfile,
)
from .redflags import RedFlagRegistry


def calculate_judge_weights(profile: JuryProfile) -> dict[str, float]:
    active = [judge for judge in profile.judges if judge.enabled]
    llm = [judge for judge in active if judge.type == JudgeType.LLM]
    human = [judge for judge in active if judge.type == JudgeType.HUMAN]

    weights: dict[str, float] = {}

    if llm:
        individual = profile.group_weights.llm / 100 / len(llm)
        weights.update({judge.id: individual for judge in llm})

    if human:
        individual = profile.group_weights.human / 100 / len(human)
        weights.update({judge.id: individual for judge in human})

    return weights


def aggregate_record(
    record: EvaluationRecord,
    registry: RedFlagRegistry,
) -> EvaluationRecord:
    profile = record.profile_snapshot
    active_judges = [judge for judge in profile.judges if judge.enabled]
    reports_by_id = {report.judge_id: report for report in record.reports}
    process_errors: list[str] = []

    missing_human = [
        judge.id
        for judge in active_judges
        if judge.type == JudgeType.HUMAN and judge.id not in reports_by_id
    ]
    missing_llm = [
        judge.id
        for judge in active_judges
        if judge.type == JudgeType.LLM and judge.id not in reports_by_id
    ]
    error_reports = [
        report
        for report in record.reports
        if report.status == "error"
    ]

    if missing_llm:
        process_errors.append(
            "Juízes LLM sem relatório: " + ", ".join(missing_llm)
        )
    if error_reports:
        process_errors.extend(
            f"{report.judge_id}: {report.error}"
            for report in error_reports
        )

    record.process_errors = list(dict.fromkeys(process_errors))

    if process_errors:
        record.status = EvaluationStatus.PROCESS_ERROR
        record.final_action = FinalAction.FALHA_DE_PROCESSO
        record.aggregated_flags = []
        record.updated_at = datetime.now(timezone.utc).isoformat()
        return record

    if missing_human and profile.require_complete_jury:
        record.status = EvaluationStatus.WAITING_HUMAN
        record.final_action = FinalAction.AGUARDANDO_JUIZ_HUMANO
        record.aggregated_flags = []
        record.updated_at = datetime.now(timezone.utc).isoformat()
        return record

    weights = calculate_judge_weights(profile)
    findings_by_flag: dict[str, list[tuple[JudgeReport, object]]] = defaultdict(list)

    selected_ids = {selection.red_flag_id for selection in profile.red_flags}

    for report in record.reports:
        if report.status != "completed":
            continue

        report_ids = [finding.red_flag_id for finding in report.findings]
        if set(report_ids) != selected_ids or len(report_ids) != len(selected_ids):
            record.status = EvaluationStatus.PROCESS_ERROR
            record.final_action = FinalAction.FALHA_DE_PROCESSO
            record.process_errors = [
                f"Relatório incompleto do juiz {report.judge_id}. "
                f"Esperado: {sorted(selected_ids)}; recebido: {sorted(report_ids)}"
            ]
            record.aggregated_flags = []
            record.updated_at = datetime.now(timezone.utc).isoformat()
            return record

        for finding in report.findings:
            findings_by_flag[finding.red_flag_id].append((report, finding))

    aggregated: list[AggregatedRedFlag] = []

    for selection in profile.red_flags:
        definition = registry.get(selection.red_flag_id)
        threshold = (
            selection.threshold
            if selection.threshold is not None
            else profile.default_detection_threshold
        )
        blocking = (
            selection.blocking_override
            if selection.blocking_override is not None
            else definition.blocking
        )
        action = selection.action_override or definition.default_action

        weighted_score = 0.0
        supporting: list[str] = []
        opposing: list[str] = []
        evidence: list[str] = []

        for report, finding in findings_by_flag.get(selection.red_flag_id, []):
            judge_weight = weights.get(report.judge_id, 0.0)
            if finding.detected:
                weighted_score += judge_weight
                supporting.append(report.judge_id)
                evidence.extend(
                    f"{report.judge_id}: {item}" for item in finding.evidence
                )
            else:
                opposing.append(report.judge_id)

        detected = weighted_score + 1e-12 >= threshold
        disputed = (
            weighted_score > 0
            and not detected
        )

        aggregated.append(
            AggregatedRedFlag(
                red_flag_id=selection.red_flag_id,
                detected=detected,
                disputed=disputed,
                weighted_score=round(weighted_score, 6),
                threshold=threshold,
                supporting_judges=supporting,
                opposing_judges=opposing,
                evidence=evidence,
                blocking=blocking,
                action=action,
            )
        )

    detected = [
        item
        for item in aggregated
        if item.detected
    ]
    critical_disputes = [
        item
        for item in aggregated
        if item.disputed
        and (
            item.blocking
            or item.action == "BLOQUEADA"
        )
    ]

    record.aggregated_flags = aggregated
    record.status = EvaluationStatus.COMPLETED
    record.metadata["critical_disagreements"] = [
        {
            "red_flag_id": item.red_flag_id,
            "weighted_score": item.weighted_score,
            "threshold": item.threshold,
            "supporting_judges": (
                item.supporting_judges
            ),
            "opposing_judges": (
                item.opposing_judges
            ),
        }
        for item in critical_disputes
    ]

    if any(
        item.blocking
        or item.action == "BLOQUEADA"
        for item in detected
    ):
        record.final_action = FinalAction.BLOQUEADA
    elif detected or critical_disputes:
        record.final_action = FinalAction.REGENERAR
    else:
        record.final_action = FinalAction.APROVADA

    record.updated_at = datetime.now(timezone.utc).isoformat()
    return record
