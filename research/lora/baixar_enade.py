"""Baixa e renomeia as provas e gabaritos listados em enade/links.txt.

Cada linha (gerada por coletar_links_enade.js) tem o formato:
    2021 | Ciência da Computação | prova | https://download.inep.gov.br/...pdf

Uso:
    python research/lora/baixar_enade.py enade/links.txt enade/
"""
from __future__ import annotations

import sys
import time
import unicodedata
import urllib.request
from pathlib import Path


def slug(curso: str) -> str:
    t = unicodedata.normalize("NFKD", curso.casefold())
    t = "".join(c for c in t if not unicodedata.combining(c))
    if "engenharia de computacao" in t:
        base = "engenharia-computacao"
    elif "sistema" in t and "informacao" in t:
        base = "sistemas-informacao"
    elif "ciencia" in t:
        base = "ciencia-computacao"
    else:
        base = "computacao"
    return base + ("-licenciatura" if "licenciatura" in t else "")


def main(lista: str, destino: str) -> None:
    pasta = Path(destino); pasta.mkdir(parents=True, exist_ok=True)
    ok = falhas = 0
    for linha in Path(lista).read_text(encoding="utf-8").splitlines():
        partes = [p.strip() for p in linha.split("|")]
        if len(partes) != 4:
            continue
        ano, curso, tipo, url = partes
        nome = pasta / f"{ano}-{slug(curso)}-{tipo}.pdf"
        if nome.exists() and nome.stat().st_size > 0:
            print(f"já existe  {nome.name}"); ok += 1; continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (HAILA pesquisa)"})
            with urllib.request.urlopen(req, timeout=60) as r:
                dados = r.read()
            if not dados.startswith(b"%PDF"):
                raise ValueError("o link não devolveu um PDF")
            nome.write_bytes(dados)
            print(f"baixado    {nome.name} ({len(dados)//1024} KB)"); ok += 1
        except Exception as exc:
            print(f"FALHOU     {nome.name}: {exc}\n           {url}"); falhas += 1
        time.sleep(1)  # não sobrecarrega o servidor do INEP
    print(f"\n{ok} arquivos prontos em {pasta}/, {falhas} falhas")
    provas = {p.name[:-len('-prova.pdf')] for p in pasta.glob('*-prova.pdf')}
    gabs = {p.name[:-len('-gabarito.pdf')] for p in pasta.glob('*-gabarito.pdf')}
    for faltando in sorted(provas ^ gabs):
        print(f"atenção: {faltando} está sem {'gabarito' if faltando in provas else 'prova'}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
