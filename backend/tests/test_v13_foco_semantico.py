from haila.contracts import NucleoQuestao
from haila.hybrid import MemoriaDistratoresCurados, gerar_distratores_ipv4_cidr
from haila.structural import avaliar_nucleo


def codes(n):
    return {f.codigo for f in avaliar_nucleo(n)}


def nucleo(enunciado, resposta):
    return NucleoQuestao(
        enunciado=enunciado,
        resposta_correta=resposta,
        explicacao="Explicação tecnicamente consistente.",
        competencia="Redes de computadores",
        habilidade="Aplicar conceitos",
        objeto_conhecimento="IPv4",
    )


def test_memoria_reconhece_atributo_de_qualidade():
    memoria = MemoriaDistratoresCurados(dataset="/arquivo/inexistente.jsonl")
    recuperado = memoria.recuperar("Atributo de qualidade")
    assert recuperado is not None
    ds, prov = recuperado
    textos = [d.texto for d in ds]
    assert len(textos) == 4
    assert "Requisito funcional" in textos
    assert "Requisito de desempenho" not in textos
    assert prov["modelo"] == "slm-memory-curated-v1"


def test_subdivisao_quatro_partes_de_24_exige_26():
    n = nucleo(
        "Uma empresa possui a rede IPv4 200.100.50.0/24 e pretende dividir "
        "o bloco em quatro sub-redes iguais. Qual prefixo deve usar?",
        "/27",
    )
    assert "gabarito_ipv4_inconsistente" in codes(n)


def test_subdivisao_quatro_partes_de_24_aceita_26():
    n = nucleo(
        "Uma empresa possui a rede IPv4 200.100.50.0/24 e pretende dividir "
        "o bloco em quatro sub-redes iguais. Qual prefixo deve usar?",
        "/26",
    )
    assert "gabarito_ipv4_inconsistente" not in codes(n)


def test_bloqueia_resposta_ipv4_com_duas_decisoes():
    n = nucleo(
        "Uma empresa possui a rede IPv4 200.100.50.0/24 e pretende dividir "
        "o bloco em quatro sub-redes iguais e configurar o encaminhamento para "
        "uma rede externa. Qual mecanismo de endereçamento e roteamento deve ser usado?",
        "CIDR /26 com rota fixa",
    )
    assert "questao_multiconceito" in codes(n)


def test_rota_ipv4_nao_transforma_resposta_combinada_em_prefixos():
    ds = gerar_distratores_ipv4_cidr(
        "CIDR /26 com rota fixa",
        "Uma rede IPv4 será subdividida.",
    )
    assert ds is None
