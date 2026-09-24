from __future__ import annotations

import json
import re
from pathlib import Path


def extrair_nucleo_do_prompt(prompt: str) -> tuple[str, str]:
    """Extrai enunciado e gabarito do prompt canônico de distratores."""
    resultado = re.search(
        r"### Questao:\n(.*?)\n\n### Resposta correta:\n(.*?)\n\n### Saida:",
        str(prompt),
        re.DOTALL,
    )
    if not resultado:
        raise ValueError("prompt_fora_do_contrato")
    enunciado, resposta = (parte.strip() for parte in resultado.groups())
    if not enunciado or not resposta:
        raise ValueError("prompt_sem_enunciado_ou_gabarito")
    return enunciado, resposta


def carregar_quarentena(caminho: str | Path | None) -> dict[str, str]:
    """Lê itens não avaliáveis sem alterar o conjunto de teste congelado."""
    if not caminho:
        return {}
    path = Path(caminho)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    itens = payload.get("items", []) if isinstance(payload, dict) else payload
    if not isinstance(itens, list):
        raise ValueError("quarentena_deve_conter_lista_items")
    resultado: dict[str, str] = {}
    for item in itens:
        if not isinstance(item, dict) or not item.get("id") or not item.get("reason"):
            raise ValueError("item_de_quarentena_invalido")
        resultado[str(item["id"])] = str(item["reason"])
    return resultado
