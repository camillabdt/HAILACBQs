from haila.contracts import DistratorGerado, NucleoQuestao
from haila.generator import normalizar_distratores_parciais
from haila.hybrid import MemoriaDistratoresCurados
from haila.structural import _corrupcao_lexical, avaliar_distratores


def codigos(flags):
    return {f.codigo for f in flags}


def nucleo(resposta):
    return NucleoQuestao(
        enunciado=(
            "Um sistema permite ao usuário confirmar um pedido. "
            "Qual classificação de requisito descreve essa exigência?"
        ),
        resposta_correta=resposta,
        explicacao="A exigência descreve comportamento observável do sistema.",
        competencia="Engenharia de requisitos",
        habilidade="Classificar requisitos",
        objeto_conhecimento="Requisitos funcionais e não funcionais",
    )


def test_memoria_curada_requisito_funcional():
    memoria = MemoriaDistratoresCurados(dataset="/arquivo/inexistente.jsonl")
    recuperado = memoria.recuperar("Requisito funcional")
    assert recuperado is not None
    ds, prov = recuperado
    textos = [d.texto for d in ds]
    assert len(textos) == 4
    assert "Requisito não funcional" in textos
    assert prov["modelo"] == "slm-memory-curated-v1"


def test_oposto_nao_e_parafrase_do_gabarito():
    n = nucleo("Requisito não funcional")
    ds = [
        DistratorGerado("Requisito funcional"),
        DistratorGerado("Regra de negócio"),
        DistratorGerado("Restrição de projeto"),
        DistratorGerado("Critério de aceitação"),
    ]
    assert "distrator_parafraseia_gabarito" not in codigos(avaliar_distratores(n, ds))


def test_plural_requisitos_nao_e_corrupcao_lexical():
    n = nucleo("Requisito funcional")
    assert _corrupcao_lexical(n, "Requisitos de segurança") is None


def test_parser_reune_chaves_malformadas_do_qwen():
    data = {
        "distratos": ["A"],
        "distratodos": ["B", "C"],
        "distortores": ["D"],
        "distrator_correto": ["NÃO USAR"],
    }
    ds, norm = normalizar_distratores_parciais(data)
    assert [d.texto for d in ds] == ["A", "B", "C", "D"]
    assert all(d.texto != "NÃO USAR" for d in ds)
    assert norm
