from haila.contracts import DistratorGerado, NucleoQuestao
from haila.generator import normalizar_distratores_parciais
from haila.hybrid import (
    MemoriaDistratoresCurados,
    gerar_distratores_ipv4_cidr,
)
from haila.redflags import DeterministicRedFlagAnalyzer
from haila.structural import avaliar_distratores


def codes(flags):
    return {f.codigo for f in flags}


def test_memoria_requisito_nao_funcional():
    memoria = MemoriaDistratoresCurados(dataset="/arquivo/inexistente.jsonl")
    recuperado = memoria.recuperar("Requisito não funcional")
    assert recuperado is not None
    ds, prov = recuperado
    textos = [d.texto for d in ds]
    assert len(textos) == 4
    assert "Requisito funcional" in textos
    assert "Regra de negócio" in textos
    assert prov["modelo"] == "slm-memory-curated-v1"


def test_ipv4_decimal_aciona_regra_deterministica():
    ds = gerar_distratores_ipv4_cidr(
        "255.255.255.0",
        "Uma rede IPv4 precisa atender até 200 hosts.",
    )
    assert ds is not None
    assert len(ds) == 4
    assert all("." in d.texto for d in ds)
    assert all(d.texto != "255.255.255.0" for d in ds)


def test_parser_aceita_chave_distrator_singular():
    ds, norm = normalizar_distratores_parciais({
        "distrator": ["A", "B", "C", "D"]
    })
    assert [d.texto for d in ds] == ["A", "B", "C", "D"]
    assert "distrator->distratores" in norm


def test_barreira_rejeita_mascaras_ipv4_corrompidas():
    n = NucleoQuestao(
        enunciado="Qual máscara IPv4 atende uma sub-rede para 200 hosts?",
        resposta_correta="255.255.255.0",
        explicacao="A máscara /24 oferece 254 hosts utilizáveis.",
        competencia="Redes",
        habilidade="Aplicar subnetting",
        objeto_conhecimento="IPv4",
    )
    ds = [
        DistratorGerado("254.248.0.OO"),
        DistratorGerado("254.248.00.1"),
        DistratorGerado("None of the above"),
        DistratorGerado("192.08.1.0"),
    ]
    c = codes(avaliar_distratores(n, ds))
    assert "mascara_ipv4_invalida" in c or "distrator_tipo_incompativel_ipv4" in c


def test_iwf_empate_no_maior_tamanho_nao_bloqueia():
    q = {
        "enunciado": "Qual categoria melhor classifica a restrição apresentada?",
        "alternativas": [
            "Tecnologia base",
            "Especificações técnicas",
            "Método de teste",
            "Definição de projeto",
            "Requisito não funcional",
        ],
        "correta": 4,
    }
    flags, _ = DeterministicRedFlagAnalyzer()(q, {}, {})
    assert "iwf_gabarito_mais_longo" not in codes(flags)
