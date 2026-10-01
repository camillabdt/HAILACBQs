"""Renomeia os PDFs baixados do site do INEP para o padrão do extrator.

Coloque os arquivos com o nome original em enade/originais/ e rode:
    python research/lora/renomear_inep.py enade/originais enade/

Arquivos desconhecidos são listados para você renomear à mão
(padrão: ANO-curso-prova.pdf e ANO-curso-gabarito.pdf).
"""
import shutil
import sys
from pathlib import Path

NOMES = {
    "03_CIE_COM_BACHAREL_BAIXA.pdf": "2017-ciencia-computacao-prova.pdf",
    "03_Ciencia_da_Computacao_Bacharelado.pdf": "2017-ciencia-computacao-gabarito.pdf",
    "04_CIE_COM_LICENCIATURA_BAIXA.pdf": "2017-computacao-licenciatura-prova.pdf",
    "04_Ciencia_da_Computacao_Licenciatura.pdf": "2017-computacao-licenciatura-gabarito.pdf",
    "13_ENG_COM_BACHAREL_BAIXA.pdf": "2017-engenharia-computacao-prova.pdf",
    "13_Engenharia_de_Computacao.pdf": "2017-engenharia-computacao-gabarito.pdf",
    "14_engenharia_computacao.pdf": "2014-engenharia-computacao-prova.pdf",
    "14_gab_engenharia_computacao.pdf": "2014-engenharia-computacao-gabarito.pdf",
    "43_tecnologia_redes_computadores.pdf": "2014-redes-computadores-prova.pdf",
    "43_gab_tecnologia_redes_computadores.pdf": "2014-redes-computadores-gabarito.pdf",
    "44_TEC_RED_COM_BAIXA.pdf": "2017-redes-computadores-prova.pdf",
    "44_CST_em_Redes_de_Computadores.pdf": "2017-redes-computadores-gabarito.pdf",
    "ENGENHARIA_COMPUTACAO.pdf": "2019-engenharia-computacao-prova.pdf",
    "engenharia_de_computacao.pdf": "2019-engenharia-computacao-gabarito.pdf",
    "2021_PV_bacharelado_ciencia_computacao.pdf": "2021-ciencia-computacao-prova.pdf",
    "2021_GB_bacharelado_ciencia_computacao.pdf": "2021-ciencia-computacao-gabarito.pdf",
    "2021_PV_licenciatura_ciencia_computacao.pdf": "2021-computacao-licenciatura-prova.pdf",
    "2021_GB_licenciatura_ciencia_computacao.pdf": "2021-computacao-licenciatura-gabarito.pdf",
    "2021_PV_tecnologia_redes_computadores.pdf": "2021-redes-computadores-prova.pdf",
    "2021_GB_tecnologia_redes_computadores.pdf": "2021-redes-computadores-gabarito.pdf",
    "2023_PV_engenharia_da_computacao.pdf": "2023-engenharia-computacao-prova.pdf",
    "2023_GB_engenharia_da_computacao.pdf": "2023-engenharia-computacao-gabarito.pdf",
}


def main(origem: str, destino: str) -> None:
    origem, destino = Path(origem), Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    for pdf in sorted(origem.glob("*.pdf")):
        nome = NOMES.get(pdf.name)
        if nome:
            shutil.copy(pdf, destino / nome)
            print(f"{pdf.name:45} -> {nome}")
        else:
            print(f"{pdf.name:45} -> (desconhecido: renomeie à mão)")


if __name__ == "__main__":
    main(*sys.argv[1:3])
