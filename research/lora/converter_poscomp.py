"""Converte o POSCOMP Dataset (Zenodo 10.5281/zenodo.17570916, CC BY 4.0) para questoes.jsonl.

Fonte: 1.340 questões objetivas do POSCOMP (2002–2024), sem as dependentes de
imagem. Cite: da Silva Araujo Junior, J. R.; dos Santos Lima, K. N.; Cavalcante
Ramos, A. L. POSCOMP Dataset. Zenodo, 2025. DOI 10.5281/zenodo.17570916.

Uso:
    python research/lora/converter_poscomp.py dados/poscomp-dataset.csv dados/questoes_poscomp.jsonl

Sem arquivo local, baixe com:
    curl -L -o dados/poscomp-dataset.csv "https://zenodo.org/records/17570916/files/dataset.csv?download=1"

Por padrão, as questões de Matemática ficam de fora (--incluir-matematica para mantê-las):
o ENADE de Computação, alvo da HAILA, quase não cobra matemática pura.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

MD5_ZENODO = "3dbe6ee2fbe74c6708714dcd2ce32b30"
PREFIXO = re.compile(r"^\s*\(?[a-eA-E]\s*[\)\.\-–]\s*")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", type=Path)
    ap.add_argument("saida", type=Path)
    ap.add_argument("--incluir-matematica", action="store_true")
    args = ap.parse_args()

    md5 = hashlib.md5(args.csv.read_bytes()).hexdigest()
    if md5 != MD5_ZENODO:
        print(f"aviso: md5 {md5} difere da versão 1.0.0 do Zenodo ({MD5_ZENODO})")

    saida, descartes = [], Counter()
    with args.csv.open(encoding="utf-8") as f:
        for linha in csv.DictReader(f):
            area = linha["knowledge_area"].strip()
            if area == "Matemática" and not args.incluir_matematica:
                descartes["matematica"] += 1
                continue
            chave = linha["key"].strip().upper()
            if chave not in "ABCDE" or len(chave) != 1:
                descartes["anulada_ou_sem_gabarito"] += 1
                continue
            try:
                opcoes = ast.literal_eval(linha["options"])
            except (ValueError, SyntaxError):
                descartes["opcoes_ilegiveis"] += 1
                continue
            alternativas = [PREFIXO.sub("", str(o)).strip() for o in opcoes]
            if len(alternativas) != 5:
                descartes["nao_tem_5_alternativas"] += 1
                continue
            saida.append({
                "id": f"poscomp-{linha['id']}",
                "enunciado": linha["stem"].strip(),
                "alternativas": alternativas,
                "correta": "ABCDE".index(chave),
                "fonte": f"POSCOMP {linha['year']}",
                "objeto_conhecimento": linha["area"].strip() or None,
                "subarea": linha["subarea"].strip() or None,
                "area_poscomp": area,
                "tem_imagem": False,
            })

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text("".join(json.dumps(q, ensure_ascii=False) + "\n" for q in saida), encoding="utf-8")
    print(f"{len(saida)} questões em {args.saida}; descartadas: {dict(descartes)}")
    print("por área:", dict(Counter(q["area_poscomp"] for q in saida)))


if __name__ == "__main__":
    main()
