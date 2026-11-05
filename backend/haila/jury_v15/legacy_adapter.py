from __future__ import annotations

from typing import Any

from .models import QuestionPayload


def final_distractors(record: dict[str, Any]) -> list[str]:
    history = record.get("historico_regeneracao") or []
    if isinstance(history, list) and history:
        last = history[-1]
        if isinstance(last, dict) and isinstance(last.get("distratores"), list):
            return [str(item).strip() for item in last["distratores"]]

    distractors = record.get("distratores") or []
    if not isinstance(distractors, list):
        distractors = []
    return [str(item).strip() for item in distractors]


def question_from_legacy(record: dict[str, Any]) -> QuestionPayload:
    return QuestionPayload(
        uid=str(record.get("uid") or record.get("indice_lote") or ""),
        area=str(record.get("area") or ""),
        year=record.get("ano"),
        context=str(record.get("contexto") or ""),
        statement=str(record.get("enunciado") or ""),
        answer_key=str(record.get("resposta_correta") or ""),
        distractors=final_distractors(record),
    )



def metadata_from_legacy(record: dict[str, Any]) -> dict[str, Any]:
    """Preserva rastreabilidade sem duplicar o texto completo da questão."""
    return {
        "indice_lote": record.get("indice_lote"),
        "status_entrada": record.get("status"),
        "status_cbq_anterior": record.get("status_cbq_final"),
        "status_antes_regeneracao": record.get(
            "status_antes_regeneracao"
        ),
        "rodadas_regeneracao": record.get(
            "rodadas_regeneracao", 0
        ),
        "modelo_base": record.get("modelo_base"),
        "adapter": record.get("adapter"),
        "origem_uid": record.get("uid"),
        "flags_estruturais_anteriores": record.get(
            "flags", []
        ),
    }
