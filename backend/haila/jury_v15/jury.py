from __future__ import annotations

from pathlib import Path

from .models import JuryProfile
from .redflags import RedFlagRegistry
from .repository import JsonObjectRepository


class JuryProfileService:
    def __init__(
        self,
        path: Path,
        redflags: RedFlagRegistry,
    ) -> None:
        self.repository = JsonObjectRepository(path, JuryProfile)
        self.redflags = redflags

    def create(self, profile: JuryProfile) -> JuryProfile:
        for selection in profile.red_flags:
            definition = self.redflags.get(selection.red_flag_id)
            if not definition.active:
                raise ValueError(
                    f"Red Flag inativa no perfil: {selection.red_flag_id}"
                )
        return self.repository.upsert(profile)

    def get(self, profile_id: str) -> JuryProfile:
        return self.repository.get(profile_id)

    def list(self) -> list[JuryProfile]:
        return self.repository.list()
