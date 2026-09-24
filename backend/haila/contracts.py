from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReferenciaRAG:
    id: str
    texto: str
    exame: str = "ENADE"
    ano: int | None = None
    metadados: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True)
class NucleoQuestao:
    enunciado: str
    resposta_correta: str
    explicacao: str
    competencia: str = ""
    habilidade: str = ""
    objeto_conhecimento: str = ""
    tem_imagem: bool = False
    recurso_visual: str | None = None

    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True)
class DistratorGerado:
    texto: str
    erro: str = ""
    por_que_e_falso: str = ""

    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True)
class RedFlag:
    codigo: str
    etapa: str
    campo: str
    evidencia: str
    reparo: str  # NUCLEO ou DISTRATORES

    def to_dict(self) -> dict[str, str]: return asdict(self)
