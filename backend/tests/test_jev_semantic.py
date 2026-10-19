import pytest

from haila.jev import JevSemanticEvaluator


QUESTION = {
    "enunciado": "Qual conceito explica o cenario?",
    "alternativas": ["A", "B", "C", "D", "E"],
    "correta": 2,
    "explicacao": "C e correta.",
}
SPEC = {
    "objetivo_pedagogico": "Distinguir conceitos.",
    "competencia": "Analisar.",
    "habilidade": "Classificar.",
    "objeto_conhecimento": "Computacao.",
    "dificuldade": 3,
}
REFERENCE = {"id": "ref-1", "texto": "Referencia curta."}


def fake_response(values=None):
    values = values or {
        "gabarito_unico": 0.97,
        "enunciado_claro": 0.93,
        "alinhamento_pedagogico": 0.91,
        "distratores_plausiveis": 0.88,
        "sem_ambiguidade": 0.95,
    }
    return {
        "model": "jev-1.13.0",
        "answers": {
            key: {"type": "noul", "noul": value}
            for key, value in values.items()
        },
        "usage": {"input_tokens": 321, "output_tokens": 5},
    }


def test_shadow_only_observes():
    evaluator = JevSemanticEvaluator(
        api_key="fake",
        mode="shadow",
        input_price_per_million=0.042,
        transport=lambda payload: fake_response(),
    )
    result, provenance = evaluator(QUESTION, SPEC, REFERENCE)
    assert result["criteria"]["gabarito_unico"]["decision"] == "OBSERVE"
    assert result["requires_human_review"] is None
    assert result["lowest_criterion"] == "distratores_plausiveis"
    assert result["minimum_probability"] == 0.88
    assert evaluator.blocking_flags(result) == []
    assert provenance["usage"]["input_tokens"] == 321
    assert provenance["estimated_cost_usd"] > 0


def test_gate_requires_explicit_threshold():
    with pytest.raises(RuntimeError):
        JevSemanticEvaluator(
            api_key="fake",
            mode="gate",
            transport=lambda payload: fake_response(),
        )


def test_gate_repair_target_for_distractors():
    values = {
        "gabarito_unico": 0.96,
        "enunciado_claro": 0.95,
        "alinhamento_pedagogico": 0.94,
        "distratores_plausiveis": 0.41,
        "sem_ambiguidade": 0.91,
    }
    evaluator = JevSemanticEvaluator(
        api_key="fake",
        mode="gate",
        pass_threshold=0.85,
        review_threshold=0.70,
        transport=lambda payload: fake_response(values),
    )
    result, _ = evaluator(QUESTION, SPEC, REFERENCE)
    flags = evaluator.blocking_flags(result)
    assert result["requires_human_review"] is True
    assert result["lowest_criterion"] == "distratores_plausiveis"
    assert len(flags) == 1
    assert flags[0].codigo == "jev_distratores_plausiveis"
    assert flags[0].reparo == "DISTRATORES"


def test_review_does_not_regenerate():
    values = {
        "gabarito_unico": 0.96,
        "enunciado_claro": 0.80,
        "alinhamento_pedagogico": 0.94,
        "distratores_plausiveis": 0.90,
        "sem_ambiguidade": 0.91,
    }
    evaluator = JevSemanticEvaluator(
        api_key="fake",
        mode="gate",
        pass_threshold=0.85,
        review_threshold=0.70,
        transport=lambda payload: fake_response(values),
    )
    result, _ = evaluator(QUESTION, SPEC, REFERENCE)
    assert result["criteria"]["enunciado_claro"]["decision"] == "REVIEW"
    assert evaluator.blocking_flags(result) == []


def test_one_call_has_five_noul_questions():
    captured = {}

    def transport(payload):
        captured.update(payload)
        return fake_response()

    evaluator = JevSemanticEvaluator(
        api_key="fake",
        mode="shadow",
        transport=transport,
    )
    evaluator(QUESTION, SPEC, REFERENCE)

    assert captured["model"] == "jev-latest"
    assert len(captured["questions"]) == 5
    assert all(
        item["type"] == "noul"
        for item in captured["questions"].values()
    )
    assert captured["state"]["question"]["gabarito_texto"] == "C"
