from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from .models import CustomRedFlagCreate, RedFlagDefinition


BUILTIN_FLAGS = [
    RedFlagDefinition(
        id="RF1",
        base_id="RF1",
        version=1,
        name="Erro de gabarito",
        description="O gabarito informado não corresponde à resposta correta.",
        category="correcao",
        prompt_instruction=(
            "Verifique se a resposta indicada como gabarito é realmente correta "
            "e se nenhum distrator deveria ocupar seu lugar."
        ),
        blocking=True,
        default_action="BLOQUEADA",
    ),
    RedFlagDefinition(
        id="RF2",
        base_id="RF2",
        version=1,
        name="Complexidade inadequada",
        description="A dificuldade não é compatível com o nível ou objetivo informado.",
        category="pedagogica",
        prompt_instruction=(
            "Avalie se a complexidade é adequada à área, ao nível e à habilidade "
            "que a questão pretende medir."
        ),
    ),
    RedFlagDefinition(
        id="RF3",
        base_id="RF3",
        version=1,
        name="Contradição interna",
        description="Partes da questão se contradizem.",
        category="correcao",
        prompt_instruction=(
            "Procure contradições entre contexto, enunciado, gabarito e alternativas."
        ),
        blocking=True,
        default_action="BLOQUEADA",
    ),
    RedFlagDefinition(
        id="RF4",
        base_id="RF4",
        version=1,
        name="Falta de clareza",
        description="O enunciado ou as alternativas são ambíguos ou pouco claros.",
        category="clareza",
        prompt_instruction=(
            "Verifique ambiguidade, referências vagas, formulações incompletas "
            "e mais de uma interpretação razoável."
        ),
    ),
    RedFlagDefinition(
        id="RF5",
        base_id="RF5",
        version=1,
        name="Falta de contexto",
        description="Faltam informações necessárias para responder.",
        category="respondibilidade",
        prompt_instruction=(
            "Verifique se todas as informações necessárias para resolver a questão "
            "estão presentes e acessíveis."
        ),
    ),
    RedFlagDefinition(
        id="RF6",
        base_id="RF6",
        version=1,
        name="Problemas linguísticos",
        description="Há erros gramaticais, ortográficos ou de fluidez.",
        category="linguistica",
        prompt_instruction=(
            "Avalie gramática, ortografia, concordância, fluidez e adequação vocabular."
        ),
    ),
    RedFlagDefinition(
        id="RF7",
        base_id="RF7",
        version=1,
        name="Avaliação pouco clara",
        description="Não está claro o que a questão mede ou como avaliar a resposta.",
        category="pedagogica",
        prompt_instruction=(
            "Verifique se a habilidade avaliada e o critério para identificar "
            "a resposta correta são claros."
        ),
    ),
    RedFlagDefinition(
        id="RF8",
        base_id="RF8",
        version=1,
        name="Distratores fracos",
        description="Os distratores são implausíveis, óbvios ou inadequados.",
        category="distratores",
        prompt_instruction=(
            "Avalie plausibilidade, homogeneidade, pistas, repetição, paráfrase "
            "do gabarito e possibilidade de segunda resposta correta."
        ),
    ),
]


def _slug(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", ascii_text).strip("_").upper()
    return slug[:48] or "CUSTOM"


class RedFlagRegistry:
    def __init__(self, custom_path: Path) -> None:
        self.custom_path = custom_path
        self.custom_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_custom(self) -> list[RedFlagDefinition]:
        if not self.custom_path.exists():
            return []
        data = json.loads(self.custom_path.read_text(encoding="utf-8"))
        return [RedFlagDefinition.model_validate(item) for item in data]

    def _save_custom(self, flags: list[RedFlagDefinition]) -> None:
        self.custom_path.write_text(
            json.dumps(
                [item.model_dump(mode="json") for item in flags],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def list(self, active_only: bool = True) -> list[RedFlagDefinition]:
        items = BUILTIN_FLAGS + self._load_custom()
        if active_only:
            items = [item for item in items if item.active]
        return items

    def get(self, red_flag_id: str) -> RedFlagDefinition:
        for item in self.list(active_only=False):
            if item.id == red_flag_id:
                return item
        raise KeyError(f"Red Flag não encontrada: {red_flag_id}")

    def create_custom(self, payload: CustomRedFlagCreate) -> RedFlagDefinition:
        custom = self._load_custom()
        base_id = payload.base_id or f"RF_CUSTOM_{_slug(payload.name)}"
        existing = [item for item in custom if item.base_id == base_id]
        version = max((item.version for item in existing), default=0) + 1

        for item in custom:
            if item.base_id == base_id:
                item.active = False

        item = RedFlagDefinition(
            id=f"{base_id}_V{version}",
            base_id=base_id,
            version=version,
            name=payload.name,
            description=payload.description,
            category=payload.category,
            prompt_instruction=payload.prompt_instruction,
            blocking=payload.blocking,
            default_action=payload.default_action,
            source="custom",
            created_by=payload.created_by,
            active=True,
        )
        custom.append(item)
        self._save_custom(custom)
        return item
