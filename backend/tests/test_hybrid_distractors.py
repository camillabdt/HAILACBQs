from haila.contracts import NucleoQuestao
from haila.hybrid import HybridDistractorGenerator


class SlmQueNaoDeveSerChamado:
    model = "test-double"

    def __call__(self, nucleo, feedback):
        raise AssertionError("família curada deveria atender este gabarito")


def gerar(resposta):
    nucleo = NucleoQuestao(
        "Considere o cenário descrito e selecione a alternativa correta.",
        resposta,
        "Explicação do conceito.",
        "Computação",
        "Analisar",
        "Conteúdo específico",
    )
    return HybridDistractorGenerator(
        SlmQueNaoDeveSerChamado(), use_memory=True, use_rules=True
    )(nucleo, [])


def test_memoria_curada_cobre_respostas_do_piloto():
    for resposta in ("Nenhuma", "UDP", "Não funcional", "Fila", "Aprendizado não supervisionado"):
        distratores, provenance = gerar(resposta)
        assert len(distratores) == 4
        assert resposta.casefold() not in {d.texto.casefold() for d in distratores}
        assert provenance["estrategia"] == "familia_conceitual_curada"
