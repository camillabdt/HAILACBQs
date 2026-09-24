from haila.redflags import DeterministicRedFlagAnalyzer


def test_item_limpo_nao_gera_red_flag():
    flags, provenance = DeterministicRedFlagAnalyzer()(
        {
            "enunciado": "Considere uma situação suficientemente descrita para a questão.",
            "alternativas": ["A", "B", "C", "D", "E"],
            "tem_imagem": False,
        },
        {},
        {},
    )
    assert flags == []
    assert provenance["tipo"] == "deterministico"


def test_placeholder_residual_e_bloqueado():
    analyzer = DeterministicRedFlagAnalyzer()
    question = {
        "enunciado": "Qual propriedade descreve o cenário apresentado?",
        "alternativas": ["Atomicidade", "<NAME>", "Isolamento", "Consistência", "Durabilidade"],
        "correta": 0,
        "tem_imagem": False,
        "recurso_visual": None,
    }
    flags, _ = analyzer(question, {}, None)
    assert "placeholder_residual" in {item.codigo for item in flags}


def test_dependencia_visual_ausente_e_bloqueada():
    flags, _ = DeterministicRedFlagAnalyzer()(
        {"enunciado": "Observe a figura e responda.", "alternativas": ["A", "B", "C", "D", "E"], "tem_imagem": True},
        {},
        {},
    )
    assert {flag.codigo for flag in flags} == {"dependencia_visual_ausente"}
