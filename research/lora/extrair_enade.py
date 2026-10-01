"""Extrai questões objetivas de provas do ENADE (PDF do INEP) para questoes.jsonl.

Organize os arquivos assim (um par por prova):

    enade/2021-ciencia-computacao-prova.pdf
    enade/2021-ciencia-computacao-gabarito.pdf
    enade/2017-engenharia-computacao-prova.pdf
    enade/2017-engenharia-computacao-gabarito.csv     <- opcional, ver abaixo

e rode:

    pip install pdfplumber
    python research/lora/extrair_enade.py enade/ questoes.jsonl

Saídas:
- questoes.jsonl: entrada para preparar_dados.py;
- questoes_revisao.csv: itens que o extrator não teve certeza de ter lido bem.
  Abra no Excel, confira os marcados e corrija ou apague as linhas no jsonl.

Gabarito: o script tenta ler o PDF do gabarito definitivo. Se um PDF trouxer
vários cursos ou a leitura falhar, crie um CSV com o mesmo prefixo
(...-gabarito.csv) no formato "questao,gabarito" (ex.: 9,C), usando ANULADA
para questões anuladas. O CSV tem prioridade sobre o PDF.

Por padrão, só entram as questões objetivas do componente específico (9 a 35);
as de formação geral (1 a 8) não tratam de Computação.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

LETRAS = "ABCDE"
CABECALHO = re.compile(r"^\s*QUEST[ÃA]O\s+(\d{1,2})\s*$", re.I | re.M)
DISCURSIVA = re.compile(r"QUEST[ÃA]O\s+DISCURSIVA", re.I)
ALTERNATIVA = re.compile(r"^\s*\(?([A-E])\s*[\)\.\-–]?\s+(\S.*)$")
LIXO = re.compile(
    r"^\s*(\*[A-Z0-9]+\*|[ÁA]REA LIVRE|RASCUNHO|ENADE\s*\d{4}|\d{1,2}\s*$|"
    r"P[ÁA]GINA\s+\d+|CI[ÊE]NCIA DA COMPUTA[ÇC][ÃA]O.*BACHARELADO|"
    r"ENGENHARIA DE COMPUTA[ÇC][ÃA]O\s*$|SISTEMAS DE INFORMA[ÇC][ÃA]O\s*$)",
    re.I,
)
VISUAL = re.compile(r"\b(figura|imagem|gr[aá]fico|diagrama|esquema a seguir|tabela a seguir|ilustra)", re.I)


# --------------------------------------------------------------------------- PDF
def texto_da_pagina(pagina) -> str:
    """Lê a página respeitando duas colunas quando houver uma faixa vazia no meio.

    A detecção usa caracteres, não palavras: nas provas com a fonte sem
    ToUnicode o espaço é um glifo comum, e uma linha inteira vira uma "palavra".
    """
    largura = pagina.width
    meio = largura / 2
    visiveis = [c for c in pagina.chars if c["text"].strip()]
    faixa = [c for c in visiveis if c["x0"] < meio + 3 and c["x1"] > meio - 3]
    esquerda = sum(1 for c in visiveis if c["x1"] <= meio)
    direita = sum(1 for c in visiveis if c["x0"] >= meio)
    duas_colunas = len(faixa) <= max(3, 0.01 * len(visiveis)) and esquerda > 150 and direita > 150
    if not duas_colunas:
        return pagina.extract_text() or ""
    a = pagina.crop((0, 0, meio, pagina.height)).extract_text() or ""
    b = pagina.crop((meio, 0, largura, pagina.height)).extract_text() or ""
    return a + "\n" + b


# As provas de 2014 e 2017 embutem a Calibri sem tabela ToUnicode: o texto sai
# como índices de glifo, "(cid:258)" etc. O mapa abaixo foi obtido alinhando o
# texto dessas provas ao OCR das páginas renderizadas (concordância >= 0,8 por
# glifo) e completado com as ligaduras da Calibri (fi, ti, tt...) pelo contexto.
MAPA_GID = {int(k): v for k, v in json.loads(
    (Path(__file__).with_name("mapa_calibri_gid.json")).read_text(encoding="utf-8")).items()}
DESCONHECIDO = "\ufffd"


CID = re.compile(r"\(cid:(\d+)\)")


def decodificar_cid(texto: str) -> str:
    """Decodificação só por texto (sem saber a fonte); usada no gabarito."""
    return CID.sub(lambda m: MAPA_GID.get(int(m.group(1)), DESCONHECIDO), texto)


def decodificar_caracteres(pagina) -> None:
    """Troca, caractere a caractere, "(cid:N)" pelo texto conforme a fonte.

    Calibri usa o mapa aprendido; Courier New segue a ordem padrão de glifos
    TrueType (glifo = código ASCII - 29); outras fontes (Symbol) ficam como
    desconhecidas, e o item é excluído depois.
    """
    for c in pagina.chars:
        m = CID.fullmatch(c["text"])
        if not m:
            continue
        gid, fonte = int(m.group(1)), c.get("fontname", "")
        if "Calibri" in fonte:
            c["text"] = MAPA_GID.get(gid, DESCONHECIDO)
        elif "Courier" in fonte and 3 <= gid <= 97:
            c["text"] = chr(gid + 29)
        else:
            c["text"] = DESCONHECIDO


def ler_pdf(caminho: Path) -> str:
    import pdfplumber

    with pdfplumber.open(str(caminho)) as pdf:
        partes = []
        for p in pdf.pages:
            decodificar_caracteres(p)
            partes.append(texto_da_pagina(p))
        return "\n".join(partes)


# ------------------------------------------------------------------- questões
def limpar(linhas: list[str]) -> list[str]:
    return [l.rstrip() for l in linhas if l.strip() and not LIXO.match(l)]


def separar_alternativas(bloco: str) -> tuple[str, list[str]] | None:
    """Encontra a última sequência A..E no início de linhas e divide o bloco."""
    linhas = limpar(bloco.splitlines())
    # Em algumas provas a letra da alternativa fica numa linha e o texto na seguinte.
    juntas: list[str] = []
    for linha in linhas:
        if juntas and re.fullmatch(r"\s*\(?[A-E]\)?\s*", juntas[-1]):
            juntas[-1] = juntas[-1].strip() + " " + linha.strip()
        else:
            juntas.append(linha)
    linhas = juntas
    marcas = [(i, m.group(1)) for i, l in enumerate(linhas) if (m := ALTERNATIVA.match(l))]
    # Procura de trás para frente uma sequência A, B, C, D, E em ordem.
    for inicio in range(len(marcas) - 1, -1, -1):
        if marcas[inicio][1] != "A":
            continue
        seq, esperada = [], 0
        for i, letra in marcas[inicio:]:
            if letra == LETRAS[esperada]:
                seq.append(i); esperada += 1
                if esperada == 5:
                    break
        if esperada < 5:
            continue
        enunciado = " ".join(l.strip() for l in linhas[: seq[0]])
        alternativas = []
        for k, i in enumerate(seq):
            fim = seq[k + 1] if k < 4 else len(linhas)
            primeira = ALTERNATIVA.match(linhas[i]).group(2)
            resto = [l.strip() for l in linhas[i + 1: fim]]
            alternativas.append(" ".join([primeira, *resto]).strip())
        return re.sub(r"\s+", " ", enunciado).strip(), [limpar_cauda(a, alternativas) for a in alternativas]
    return None


CORTE = re.compile(r"\s(?:QUEST[ÃA]O\s+\d|[ÁA]REA LIVRE|RASCUNHO|\*[A-Z]\d|[–-]\s*DISCURSIVA)", re.I)


def limpar_cauda(alternativa: str, todas: list[str]) -> str:
    """Remove restos de cabeçalho/rodapé grudados no fim de uma alternativa."""
    a = CORTE.split(alternativa)[0].strip()
    pontuadas = sum(bool(re.search(r"[.;?!)]$", x.strip())) for x in todas)
    m = re.match(r"^(.*[.;?!)])\s+(\S+(?:\s+\S+){0,3})$", a)
    if m and pontuadas >= 3 and not re.search(r"[.;?!)]", m.group(2)):
        a = m.group(1)
    return a


def extrair_questoes(texto: str) -> dict[int, str]:
    """Divide o texto da prova em blocos por número de questão objetiva."""
    partes = list(CABECALHO.finditer(texto))
    blocos: dict[int, str] = {}
    for k, m in enumerate(partes):
        fim = partes[k + 1].start() if k + 1 < len(partes) else len(texto)
        bloco = texto[m.end(): fim]
        # Uma questão discursiva começa no meio do bloco: corta ali.
        d = DISCURSIVA.search(bloco)
        if d:
            bloco = bloco[: d.start()]
        numero = int(m.group(1))
        blocos.setdefault(numero, bloco)  # a primeira ocorrência vale (evita sumários)
    return blocos


# ------------------------------------------------------------------- gabarito
def ler_gabarito(prefixo: Path) -> tuple[dict[int, str], str]:
    csv_path = prefixo.with_name(prefixo.name + "-gabarito.csv")
    if csv_path.exists():
        with csv_path.open(encoding="utf-8-sig") as f:
            linhas = [r for r in csv.reader(f) if r and r[0].strip().isdigit()]
        return {int(q): g.strip().upper() for q, g in linhas}, "csv"
    pdf_path = prefixo.with_name(prefixo.name + "-gabarito.pdf")
    if not pdf_path.exists():
        return {}, "ausente"
    import pdfplumber

    # O gabarito é uma tabela "item | letra": ler sem separar colunas, senão o
    # número e a letra caem em colunas diferentes.
    with pdfplumber.open(str(pdf_path)) as pdf:
        texto = decodificar_cid("\n".join(p.extract_text() or "" for p in pdf.pages)).upper()
    pares = re.findall(r"(?<!DISCURSIVA )\b(\d{1,2})\s*[-–:]?\s*(ANULADA|[A-E])\b", texto)
    gabarito: dict[int, str] = {}
    conflitos = 0
    for q, g in pares:
        q = int(q)
        if q in gabarito and gabarito[q] != g:
            conflitos += 1
        gabarito.setdefault(q, g)
    return gabarito, ("pdf" if not conflitos else f"pdf_{conflitos}_conflitos")


# ---------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pasta", type=Path)
    ap.add_argument("saida", type=Path)
    ap.add_argument("--incluir-formacao-geral", action="store_true")
    ap.add_argument("--primeira-especifica", type=int, default=9)
    args = ap.parse_args()

    provas = sorted(args.pasta.glob("*-prova.pdf"))
    if not provas:
        raise SystemExit(f"nenhum arquivo *-prova.pdf em {args.pasta}")

    saida, revisao, resumo = [], [], []
    for prova in provas:
        prefixo = prova.with_name(prova.name[: -len("-prova.pdf")])
        fonte = prefixo.name
        gabarito, origem_gab = ler_gabarito(prefixo)
        texto_prova = re.sub(r"\S*(?:VALID|INEP20\d\d)\S*", "", ler_pdf(prova))  # marca d'água de 2023
        blocos = extrair_questoes(texto_prova)
        # O primeiro item do componente específico muda entre edições (9 até
        # 2021, 10 em 2023): usa a primeira questão após o título da seção.
        primeira = args.primeira_especifica
        secao = re.search(r"^\s*COMPONENTE ESPEC[ÍI]FICO\s*$", texto_prova, re.M)
        if secao:
            seguinte = CABECALHO.search(texto_prova, secao.end())
            if seguinte:
                primeira = int(seguinte.group(1))
        aceitas = 0
        for numero, bloco in sorted(blocos.items()):
            if numero < primeira and not args.incluir_formacao_geral:
                continue
            problemas = []
            partes = separar_alternativas(bloco)
            if not partes:
                revisao.append({"fonte": fonte, "questao": numero, "problema": "alternativas A-E não encontradas"})
                continue
            enunciado, alternativas = partes
            letra = gabarito.get(numero)
            if letra == "ANULADA":
                continue
            if not letra or letra not in LETRAS:
                revisao.append({"fonte": fonte, "questao": numero, "problema": f"gabarito ausente ({origem_gab})"})
                continue
            if DESCONHECIDO in enunciado + "".join(alternativas):
                # Trechos em outra fonte (código em Courier, símbolos) não puderam
                # ser decodificados; o item fica fora em vez de entrar corrompido.
                revisao.append({"fonte": fonte, "questao": numero, "problema": "caracteres não recuperados (excluída)"})
                continue
            if len(enunciado) < 60:
                problemas.append("enunciado curto: pode ter sido cortado")
            if any(len(a) > 400 for a in alternativas):
                problemas.append("alternativa muito longa: pode ter misturado colunas")
            if VISUAL.search(enunciado):
                problemas.append("menciona figura/tabela")
            item = {
                "id": f"{fonte}-q{numero:02d}", "enunciado": enunciado, "alternativas": alternativas,
                "correta": LETRAS.index(letra), "fonte": fonte, "numero": numero,
                "tem_imagem": bool(VISUAL.search(enunciado)), "objeto_conhecimento": None,
            }
            saida.append(item); aceitas += 1
            if problemas:
                revisao.append({"fonte": fonte, "questao": numero, "problema": "; ".join(problemas)})
        resumo.append((fonte, len(blocos), aceitas, origem_gab, len(gabarito)))

    args.saida.write_text("".join(json.dumps(q, ensure_ascii=False) + "\n" for q in saida), encoding="utf-8")
    caminho_rev = args.saida.with_name(args.saida.stem + "_revisao.csv")
    with caminho_rev.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["fonte", "questao", "problema"]); w.writeheader(); w.writerows(revisao)

    print(f"{'prova':45} blocos  extraídas  gabarito")
    for fonte, nb, na, og, ng in resumo:
        print(f"{fonte:45} {nb:6} {na:10}  {og} ({ng} respostas)")
    print(f"\nTotal: {len(saida)} questões em {args.saida}; {len(revisao)} pontos para revisar em {caminho_rev}")


if __name__ == "__main__":
    sys.exit(main())
