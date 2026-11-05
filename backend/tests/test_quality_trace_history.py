from haila.repository import _quality_trace


def test_quality_trace_separates_final_warnings_from_treated_occurrences():
    req = {"stem_attempts": 1, "distractor_attempts": 2}
    artifacts = [
        {
            "kind": "DISTRACTOR_BATCH",
            "payload": [
                {"texto": "A"}, {"texto": "B"}, {"texto": "C"},
                {"texto": "D"}, {"texto": "E"}, {"texto": "F"},
            ],
            "provenance": {},
        },
        {
            "kind": "DISTRACTOR_CANDIDATE_REJECTED",
            "payload": {"texto": "Termo artificial"},
            "provenance": {
                "flags": [
                    {
                        "codigo": "iwf_termo_absoluto",
                        "etapa": "DISTRATORES",
                        "campo": "alternativas",
                        "evidencia": "termo absoluto no candidato",
                        "reparo": "DISTRATORES",
                    }
                ]
            },
        },
        {
            "kind": "DISTRACTOR_CANDIDATE_REJECTED_QUALITY",
            "payload": {"texto": "Classe cardinalária"},
            "provenance": {
                "quality_code": "termo_nao_padronizado",
                "reason": "terminologia não padronizada para o domínio",
            },
        },
        {
            "kind": "DISTRACTOR_RESERVE_PROMOTED",
            "payload": {"texto": "Chave candidata"},
            "provenance": {"reason": "quality_rejection_replacement", "check": 1},
        },
        {
            "kind": "QUALITY_SUMMARY",
            "payload": {
                "warnings": [
                    {
                        "codigo": "iwf_termo_absoluto",
                        "etapa": "DETERMINISTICA",
                        "campo": "questao",
                        "evidencia": "termos absolutos encontrados: todo",
                        "reparo": "NUCLEO",
                    }
                ],
                "active_distractors": 4,
                "reserve_distractors": 1,
                "candidate_bank_size": 5,
            },
            "provenance": {},
        },
    ]
    flags = [
        {
            "code": "iwf_termo_absoluto",
            "stage": "DETERMINISTICA",
            "field": "questao",
            "evidence": "termos absolutos encontrados: todo",
            "repair_target": "NUCLEO",
        }
    ]
    events = [
        {"created_at": "2026-10-20T21:00:00+00:00"},
        {"created_at": "2026-10-20T21:00:30.160000+00:00"},
    ]

    trace = _quality_trace(req, artifacts, flags, events)

    assert trace["final_warning_count"] == 1
    assert trace["treated_occurrence_count"] == 2
    assert trace["reserve_promotion_count"] == 1
    assert trace["metrics"]["candidates_generated"] == 6
    assert trace["metrics"]["quality_rejections"] == 1
    assert trace["metrics"]["duration_seconds"] == 30.16
    assert trace["treated_occurrences"][1]["candidate"] == "Classe cardinalária"
    assert trace["treated_occurrences"][1]["code"] == "termo_nao_padronizado"


def test_quality_trace_without_summary_remains_backward_compatible():
    trace = _quality_trace(
        {"stem_attempts": 0, "distractor_attempts": 0},
        [],
        [],
        [],
    )
    assert trace["final_warning_count"] == 0
    assert trace["treated_occurrence_count"] == 0
    assert trace["metrics"]["duration_seconds"] is None
