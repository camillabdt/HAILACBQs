# Avaliação automática da amostra ampliada

## Desenho

A amostra contém 12 especificações congeladas, uma para cada tema do corpus RAG. A geração usa a configuração C4 completa. As questões concluídas são avaliadas com os 19 Item-Writing Flaws (IWF) do SAQUET e as oito dimensões adaptadas de Arif et al. Regras e juiz LLM permanecem identificados separadamente.

## Execução da geração

| Resultado | Quantidade |
|---|---:|
| Geração concluída | 5 |
| Tentativas esgotadas pelas salvaguardas | 1 |
| Interrompida por limite externo da Groq | 6 |
| Total planejado | 12 |

A taxa bruta de conclusão foi 5/12. Ela não deve ser interpretada como taxa de qualidade, pois metade da amostra foi interrompida por limite externo do provedor. Entre os seis casos que efetivamente puderam percorrer o motor, cinco concluíram e um foi bloqueado após esgotar as tentativas.

## Questões concluídas

| Item | Tema | IWF/SAQUET | Resultado |
|---|---|---:|---|
| E01 | Concorrência | 2 | Não aceitável |
| E02 | Memória virtual | 3 | Não aceitável |
| E04 | Estruturas de dados | parecer semântico indisponível | Pendente |
| E05 | Transações ACID | parecer semântico indisponível | Pendente |
| E07 | TCP e UDP | 0 | Aceitável |

## Falhas observadas

- E01: um distrator não representa mecanismo de sincronização plausível e a descrição contém pistas que definem diretamente mutex.
- E02: o gabarito é a alternativa mais longa, repete termos do enunciado e há distrator sem relação com memória virtual.
- E07: nenhuma IWF foi apontada; as alternativas representam combinações distintas de garantias de transporte.
- E03: o motor bloqueou sucessivamente repetição literal do gabarito e paráfrase entre distrator e resposta, terminando em `ATTEMPTS_EXHAUSTED`.

## Evidência técnica complementar

O benchmark isolado obteve 87/87 verificações: 12 consultas do RAG, 65 recuperações de famílias conceituais e 10 casos de red flags/estrutura. A suíte do backend possui 16 testes aprovados. Esses resultados demonstram conformidade nos casos de teste, mas não garantem generalização das questões.

## Limites

Esta rodada foi afetada por limite de tokens do provedor. Apenas três das cinco questões concluídas receberam o parecer semântico completo antes de novo limite. Os denominadores são sempre apresentados para evitar tratar itens não avaliados como aprovados. Sem professores, a análise automática não estabelece validade de conteúdo; sem respostas de estudantes, não estima dificuldade, discriminação ou eficiência empírica dos distratores.
