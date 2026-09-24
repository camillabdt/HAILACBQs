from haila.contracts import DistratorGerado, NucleoQuestao
from haila.structural import avaliar_distratores, avaliar_nucleo


def test_nucleo_plural_com_gabarito_singular_e_bloqueado():
    nucleo = NucleoQuestao(
        "Após uma falha antes do COMMIT, quais propriedades ACID são demonstradas pelo comportamento?",
        "Atomicidade",
        "Todas as mudanças da transação são desfeitas.",
        "Banco de dados",
        "Analisar transações",
        "Propriedades ACID",
    )
    assert "enunciado_ambiguo" in {flag.codigo for flag in avaliar_nucleo(nucleo)}


def test_distrator_duplicado_e_bloqueado():
    nucleo = NucleoQuestao("Qual propriedade resolve o cenário descrito de forma correta?", "Atomicidade", "Explicação.")
    distratores = [DistratorGerado("Isolamento"), DistratorGerado("Durabilidade"), DistratorGerado("Consistência"), DistratorGerado("Isolamento")]
    assert "distratores_duplicados" in {flag.codigo for flag in avaliar_distratores(nucleo, distratores)}


def test_nucleo_com_espaco_binario_e_reformulado():
    nucleo = NucleoQuestao(
        "Classifique o requisito apresentado como funcional ou não funcional.",
        "Não funcional",
        "O requisito descreve desempenho.",
        "Engenharia de software",
        "Classificar requisitos",
        "Engenharia de requisitos",
    )
    assert "espaco_de_respostas_binario" in {flag.codigo for flag in avaliar_nucleo(nucleo)}


def test_multiplos_requisitos_nao_funcionais_sao_bloqueados():
    nucleo = NucleoQuestao(
        "REQ1 – O usuário pode pesquisar livros; REQ2 – A busca retorna em até 2 segundos; REQ3 – O acesso exige usuário autenticado; REQ4 – O sistema suporta 500 usuários simultâneos. Qual corresponde a um requisito não funcional?",
        "REQ2",
        "REQ2 estabelece uma restrição de desempenho.",
        "Engenharia de software",
        "Classificar requisitos",
        "Engenharia de requisitos",
    )
    assert "multiplos_candidatos_ao_gabarito" in {flag.codigo for flag in avaliar_nucleo(nucleo)}


def test_escolha_aberta_de_protocolo_e_bloqueada():
    nucleo = NucleoQuestao(
        "Uma aplicação exige entrega confiável e ordenada. Qual protocolo deve ser escolhido?",
        "TCP",
        "TCP oferece entrega confiável e ordenada.",
        "Redes",
        "Comparar protocolos",
        "TCP e UDP",
    )
    assert "selecao_de_protocolo_potencialmente_ambigua" in {flag.codigo for flag in avaliar_nucleo(nucleo)}


def test_supervisionado_e_nao_supervisionado_sao_opostos_validos():
    nucleo = NucleoQuestao(
        "Sem rótulos, qual paradigma deve ser empregado para encontrar grupos nos dados?",
        "Aprendizado não supervisionado",
        "A tarefa não possui rótulos.",
        "Inteligência artificial",
        "Distinguir paradigmas",
        "Aprendizado de máquina",
    )
    distratores = [
        DistratorGerado("Aprendizado supervisionado"),
        DistratorGerado("Aprendizado por reforço"),
        DistratorGerado("Aprendizado semissupervisionado"),
        DistratorGerado("Aprendizado autossupervisionado"),
    ]
    assert "distrator_parafraseia_gabarito" not in {flag.codigo for flag in avaliar_distratores(nucleo, distratores)}


def test_gabarito_literal_no_enunciado_e_bloqueado():
    nucleo = NucleoQuestao(
        "O sistema insere documentos em uma fila de impressão. Qual estrutura deve usar?",
        "Fila",
        "A fila implementa FIFO.",
        "Algoritmos",
        "Selecionar estruturas",
        "Estruturas de dados",
    )
    assert "gabarito_repetido_no_enunciado" in {flag.codigo for flag in avaliar_nucleo(nucleo)}
