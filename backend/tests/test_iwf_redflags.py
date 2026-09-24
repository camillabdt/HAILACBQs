from haila.redflags import DeterministicRedFlagAnalyzer


def analisar(enunciado, alternativas, correta=0):
    flags, _ = DeterministicRedFlagAnalyzer()(
        {"enunciado": enunciado, "alternativas": alternativas, "correta": correta}, {}, None
    )
    return {flag.codigo for flag in flags}


def test_bloqueia_gabarito_mais_longo():
    codigos = analisar("Qual propriedade se aplica?", ["Resposta correta muito mais extensa", "Curta", "Breve", "Outra", "Menor"])
    assert "iwf_gabarito_mais_longo" in codigos


def test_bloqueia_comando_negativo_e_absoluto():
    codigos = analisar("Qual alternativa não é correta, exceto quando sempre ocorre?", ["A", "B", "C", "D", "E"])
    assert {"iwf_comando_negativo", "iwf_termo_absoluto"} <= codigos


def test_bloqueia_pista_lexical_exclusiva_do_gabarito():
    codigos = analisar("O atendimento segue comportamento FIFO. Qual estrutura usar?", ["Fila FIFO", "Pilha", "Heap", "Árvore", "Grafo"])
    assert "iwf_repeticao_entrega_gabarito" in codigos
