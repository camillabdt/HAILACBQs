from haila.iwf import deterministic_iwf, evaluate_iwf


def test_iwf_detecta_falhas_textuais_classicas():
    q={"enunciado":"Qual alternativa é sempre correta? ...","alternativas":["A","B","C","Todas as anteriores","Nenhuma das alternativas"],"correta":0}
    flags=deterministic_iwf(q)
    assert flags["absolute_terms"] is True
    assert flags["fill_in_the_blank"] is True
    assert flags["all_of_the_above"] is True
    assert flags["none_of_the_above"] is True


def test_iwf_sem_juiz_declara_criterios_semanticos_pendentes():
    q={"enunciado":"Qual estrutura implementa a disciplina FIFO no cenário descrito?","alternativas":["Fila","Pilha","Heap","Tabela hash","Árvore"],"correta":0}
    result=evaluate_iwf(q)
    assert result["classification"] == "incomplete"
    assert "more_than_one_correct" in result["unresolved"]
