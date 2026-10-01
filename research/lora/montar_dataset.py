"""Monta, de ponta a ponta, o conjunto de ajuste fino da SLM da HAILA.

    python research/lora/montar_dataset.py

Etapas (cada uma é pulada se o resultado já existir):
  1. Clona o repositório geacc/enade na versão fixada (provas de 2005 a 2021).
  2. Copia essas provas para enade/ no padrão do extrator.
  3. Renomeia os PDFs do INEP que estiverem em enade/originais/ (eles têm
     prioridade sobre os do GitHub e trazem Redes de Computadores e 2023).
  4. Extrai as questões do ENADE  -> dados/questoes_enade.jsonl
  5. Baixa o POSCOMP Dataset (Zenodo) e converte -> dados/questoes_poscomp.jsonl
  6. Gera dados/haila-lora-enade/ e dados/haila-lora-enade-poscomp/ (mesma validação ENADE)
  7. Compara os hashes com MANIFESTO_DADOS.json, para confirmar que o conjunto
     é idêntico ao usado na dissertação.

Os PDFs e os textos das questões não vão para o Git: o repositório guarda os
scripts, as versões fixadas das fontes e os hashes, e qualquer pessoa reconstrói
exatamente o mesmo conjunto.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
GEACC_URL = "https://github.com/geacc/enade.git"
GEACC_COMMIT = "a657632b72b97468c8a5eb3b433d1abb4a5511c5"
POSCOMP_URL = "https://zenodo.org/records/17570916/files/dataset.csv?download=1"


def rodar(*cmd: str) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=RAIZ)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--geacc", type=Path, default=RAIZ.parent / "geacc-enade")
    ap.add_argument("--poscomp-csv", type=Path, default=RAIZ / "dados" / "poscomp-dataset.csv")
    args = ap.parse_args()
    py = sys.executable
    enade, dados = RAIZ / "enade", RAIZ / "dados"
    enade.mkdir(exist_ok=True); dados.mkdir(exist_ok=True)

    print("\n[1/7] Provas do GitHub (geacc/enade)")
    if not args.geacc.exists():
        rodar("git", "clone", "-q", GEACC_URL, str(args.geacc))
    rodar("git", "-C", str(args.geacc), "-c", "advice.detachedHead=false", "checkout", "-q", GEACC_COMMIT)

    print("\n[2/7] Copiando para enade/")
    rodar(py, str(AQUI / "importar_geacc.py"), str(args.geacc), str(enade))

    print("\n[3/7] PDFs do INEP em enade/originais/")
    if (enade / "originais").exists():
        rodar(py, str(AQUI / "renomear_inep.py"), str(enade / "originais"), str(enade))
    else:
        print("enade/originais/ não existe; seguindo só com as provas do GitHub")

    print("\n[4/7] Extraindo questões do ENADE")
    rodar(py, str(AQUI / "extrair_enade.py"), str(enade), str(dados / "questoes_enade.jsonl"))

    print("\n[5/7] POSCOMP Dataset")
    if not args.poscomp_csv.exists():
        print(f"baixando {POSCOMP_URL}")
        with urllib.request.urlopen(POSCOMP_URL, timeout=120) as r, args.poscomp_csv.open("wb") as f:
            shutil.copyfileobj(r, f)
    rodar(py, str(AQUI / "converter_poscomp.py"), str(args.poscomp_csv), str(dados / "questoes_poscomp.jsonl"))

    print("\n[6/7] Preparando as duas variantes (validação idêntica, só ENADE)")
    enade_jsonl, poscomp_jsonl = str(dados / "questoes_enade.jsonl"), str(dados / "questoes_poscomp.jsonl")
    rodar(py, str(AQUI / "preparar_dados.py"), enade_jsonl, str(dados / "haila-lora-enade"))
    rodar(py, str(AQUI / "preparar_dados.py"), enade_jsonl, poscomp_jsonl,
          str(dados / "haila-lora-enade-poscomp"), "--repetir-enade", "3")

    print("\n[7/7] Conferindo com o manifesto")
    manifesto_path = AQUI / "MANIFESTO_DADOS.json"
    atual = {}
    for nome in ("haila-lora-enade", "haila-lora-enade-poscomp"):
        r = json.loads((dados / nome / "relatorio_dados.json").read_text(encoding="utf-8"))
        atual[nome] = {"aceitas": r["aceitas"], "sha256": r["sha256"]}
        print(f"{nome}: treino={r['aceitas']['treino']} validacao={r['aceitas']['validacao']}")
    if not manifesto_path.exists():
        print("sem manifesto: nada a comparar"); return
    esperado = json.loads(manifesto_path.read_text(encoding="utf-8"))["variantes"]
    iguais = all(atual[n]["sha256"] == esperado[n]["sha256"] for n in atual)
    print("IDÊNTICO ao conjunto do manifesto" if iguais else
          "DIFERENTE do manifesto: verifique a versão do pdfplumber e os PDFs em enade/. "
          "Se a diferença for intencional, registre o novo conjunto na dissertação.")


if __name__ == "__main__":
    main()
