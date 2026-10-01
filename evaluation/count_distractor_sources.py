"""Conta a origem dos distratores (SLM, memória curada ou regra) numa execução C4.

Uso: python evaluation/count_distractor_sources.py evaluation/results/<execucao>-c4.json

A C4 usa o HybridDistractorGenerator: formatos fechados vão para regras
determinísticas, respostas reconhecidas vão para a memória curada e o restante
vai para a SLM. Este relatório separa as três origens, tanto em todas as
tentativas quanto na versão final de cada item concluído.
"""
from __future__ import annotations

import json
import sys
from collections import Counter


def origem(prov: dict) -> str:
    modelo = str(prov.get("modelo") or prov.get("model") or "")
    if prov.get("estrategia") == "familia_conceitual_curada" or "memory-curated" in modelo:
        return "memoria_curada"
    if modelo.startswith("deterministic"):
        return "regra_deterministica"
    if "LoRA" in modelo:
        return "slm_ajustada"
    if modelo:
        return "slm_base" if modelo.endswith(":base") else f"slm({modelo})"
    return "desconhecida"


def main(caminho: str) -> None:
    dados = json.load(open(caminho, encoding="utf-8"))
    todas, finais, por_item = Counter(), Counter(), {}
    for item in dados["items"]:
        hist = item.get("history") or {}
        distr = [a for a in hist.get("artifacts", []) if a.get("kind") == "DISTRACTORS"]
        origens = [origem(a.get("provenance") or {}) for a in distr]
        todas.update(origens)
        estado = (hist.get("request") or {}).get("state")
        if estado == "GENERATION_COMPLETED" and origens:
            finais[origens[-1]] += 1
        por_item[item["spec_id"]] = {"estado": estado, "origens": origens}
    print(json.dumps({"arquivo": caminho, "todas_as_tentativas": dict(todas),
                      "versao_final_dos_concluidos": dict(finais), "por_item": por_item},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
