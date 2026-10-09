from haila.contracts import NucleoQuestao
from haila.structural import avaliar_nucleo


def codigos(nucleo):
    return {f.codigo for f in avaliar_nucleo(nucleo)}


def test_bloqueia_cenario_sem_comando_e_com_foco_ambiguo():
    n = NucleoQuestao(
        enunciado=(
            "Um sistema de gerenciamento de biblioteca deve gerar, "
            "a cada solicitação do bibliotecário, um relatório mensal "
            "contendo a quantidade de empréstimos por usuário. "
            "O relatório deve ser apresentado ao usuário em até "
            "2 segundos após a solicitação."
        ),
        resposta_correta="Requisito não funcional",
        explicacao=(
            "O limite de tempo caracteriza uma restrição "
            "não funcional de desempenho."
        ),
        competencia="Engenharia de requisitos",
        habilidade="Classificar requisitos",
        objeto_conhecimento="Requisitos funcionais e não funcionais",
    )

    flags = codigos(n)

    assert "comando_da_questao_ausente" in flags
    assert "mistura_funcional_nao_funcional_ambigua" in flags


def test_aceita_cenario_com_comando_e_foco_explicito():
    n = NucleoQuestao(
        enunciado=(
            "Em um sistema de gerenciamento de biblioteca, após o "
            "bibliotecário solicitar um relatório mensal de empréstimos, "
            "o resultado deve ser apresentado em até 2 segundos. "
            "Considerando a Engenharia de Requisitos, qual categoria "
            "melhor classifica a restrição de tempo apresentada?"
        ),
        resposta_correta="Requisito não funcional",
        explicacao=(
            "A restrição estabelece um limite de desempenho "
            "para uma funcionalidade."
        ),
        competencia="Engenharia de requisitos",
        habilidade="Classificar requisitos",
        objeto_conhecimento="Requisitos funcionais e não funcionais",
    )

    flags = codigos(n)

    assert "comando_da_questao_ausente" not in flags
    assert "mistura_funcional_nao_funcional_ambigua" not in flags


def test_comando_imperativo_sem_interrogacao_e_valido():
    n = NucleoQuestao(
        enunciado=(
            "Um sistema deve responder às consultas em até 500 ms. "
            "Assinale a categoria que melhor classifica essa "
            "restrição de desempenho."
        ),
        resposta_correta="Requisito não funcional",
        explicacao="Trata-se de uma restrição de desempenho.",
        competencia="Engenharia de requisitos",
        habilidade="Classificar requisitos",
        objeto_conhecimento="Requisitos não funcionais",
    )

    flags = codigos(n)

    assert "comando_da_questao_ausente" not in flags
