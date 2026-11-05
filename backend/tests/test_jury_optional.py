from haila.jury_integration import (
    _build_profile,
    build_question_payload_from_haila,
)


def test_jury_profile_is_llm_only_and_optional():
    profile = _build_profile()
    assert profile.group_weights.llm == 100
    assert profile.group_weights.human == 0
    assert all(j.type.value == "llm" for j in profile.judges)
    assert len(profile.judges) == 2


def test_haila_question_mapping_preserves_correct_answer_and_distractors():
    version = {
        "id": "v1",
        "question": {
            "enunciado": "Qual alternativa está correta?",
            "alternativas": ["A1", "A2", "A3", "A4", "A5"],
            "correta": 2,
            "objeto_conhecimento": "Banco de Dados",
        },
    }
    request = {
        "specification": {
            "curso": "Computação",
            "objeto_conhecimento": "Banco de Dados",
        }
    }
    history = {
        "artifacts": [
            {
                "kind": "REFERENCE",
                "payload": {"texto": "Contexto RAG", "ano": 2021},
            }
        ]
    }
    payload = build_question_payload_from_haila("r1", version, request, history)
    assert payload.statement == "Qual alternativa está correta?"
    assert payload.answer_key == "A3"
    assert payload.distractors == ["A1", "A2", "A4", "A5"]
    assert payload.context == "Contexto RAG"
    assert payload.year == 2021
