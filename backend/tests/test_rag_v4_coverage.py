import json
import pytest
from haila.rag import CorpusJsonlRAG


def _seed(tmp_path):
    p = tmp_path / "c.jsonl"
    rows = [
        {"id":"ipv4","texto_base":"IPv4 usa endereços de 32 bits. CIDR e máscara de sub-rede definem o prefixo e permitem subnetting.","area":"Redes de Computadores","objeto_conhecimento":"IPv4, sub-redes e CIDR","palavras_chave":["IPv4","subnetting","CIDR"],"exame":"ACERVO_CONCEITUAL_HAILA"},
        {"id":"tcp","texto_base":"TCP oferece entrega confiável e ordenada e usa confirmações e retransmissões.","area":"Redes de Computadores","objeto_conhecimento":"TCP","palavras_chave":["TCP"],"exame":"ACERVO_CONCEITUAL_HAILA"},
        {"id":"acid","texto_base":"Transações de bancos de dados seguem propriedades como atomicidade, isolamento e durabilidade.","area":"Banco de Dados","objeto_conhecimento":"Transações ACID","palavras_chave":["ACID"],"exame":"ACERVO_CONCEITUAL_HAILA"},
    ]
    p.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows)+"\n", encoding="utf-8")
    return p


def test_recupera_ipv4_subnetting_por_alias(tmp_path):
    rag = CorpusJsonlRAG(_seed(tmp_path))
    ref = rag({"curso":"Computação","componente":"ESPECIFICO","exame":"ENADE","objeto_conhecimento":"endereçamento IPv4 e subnetting","objetivo_pedagogico":"calcular sub-redes usando máscara e CIDR"})
    assert ref.id == "ipv4"
    assert "ipv4" in ref.texto.lower()
    assert ref.metadados["retrieval"].endswith("v4")


def test_top_k_nao_mistura_banco_com_redes(tmp_path):
    rag = CorpusJsonlRAG(_seed(tmp_path))
    ref = rag({"curso":"Computação","componente":"ESPECIFICO","exame":"ENADE","objeto_conhecimento":"TCP","objetivo_pedagogico":"analisar confiabilidade do TCP"})
    assert all(x["area"] == "Redes de Computadores" for x in ref.metadados["fontes"])


def test_tema_ausente_continua_bloqueado(tmp_path):
    rag = CorpusJsonlRAG(_seed(tmp_path))
    with pytest.raises(ValueError, match="sem referência relevante"):
        rag({"curso":"Computação","componente":"ESPECIFICO","exame":"ENADE","objeto_conhecimento":"Computação quântica","objetivo_pedagogico":"analisar correção de erros quânticos"})
