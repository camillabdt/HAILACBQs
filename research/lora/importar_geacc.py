"""Copia as provas do repositório geacc/enade para enade/ no padrão do extrator.

Uso:
    git clone https://github.com/geacc/enade.git ../geacc-enade
    python research/lora/importar_geacc.py ../geacc-enade enade/

No repositório, o prefixo indica o curso: b = Ciência da Computação,
l = Licenciatura em Computação, e = Engenharia de Computação,
s = Sistemas de Informação; sem prefixo (2011) = prova única de Computação.
"""
import re
import shutil
import sys
from pathlib import Path

CURSOS = {"b": "ciencia-computacao", "l": "computacao-licenciatura", "e": "engenharia-computacao",
          "s": "sistemas-informacao", "": "computacao"}


def main(origem: str, destino: str) -> None:
    origem, destino = Path(origem), Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    n = 0
    for prova in sorted(origem.glob("*/*1_prova.pdf")):
        ano = prova.parent.name
        m = re.fullmatch(r"([a-z]?)1_prova\.pdf", prova.name)
        if not (m and ano.isdigit()):
            continue
        gab = prova.with_name(f"{m.group(1)}2_gabarito.pdf")
        if not gab.exists():
            print(f"sem gabarito: {prova}"); continue
        base = f"{ano}-{CURSOS[m.group(1)]}"
        shutil.copy(prova, destino / f"{base}-prova.pdf")
        shutil.copy(gab, destino / f"{base}-gabarito.pdf")
        n += 1
        print(f"{base}")
    print(f"\n{n} provas copiadas para {destino}/")


if __name__ == "__main__":
    main(*sys.argv[1:3])
