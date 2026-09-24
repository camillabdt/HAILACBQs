# Resultado final do piloto C4

## Configuração avaliada

Arquitetura HAILA completa: RAG para recuperação da referência, LLM para geração do núcleo, subsistema híbrido de distratores (memória conceitual, regras e SLM local), montagem, red flags determinísticas, regeneração e persistência do histórico.

Foram usadas cinco especificações congeladas. P01, P03 e P04 vêm da rodada v3; P02 e P05 foram repetidas após as correções motivadas pela própria avaliação.

## Resultado

| Item | Tema | Resultado arquitetural | Triagem semântica assistida |
|---|---|---|---|
| P01 | Propriedades ACID | Concluída | Aproveitável |
| P02 | TCP e UDP | Bloqueada, regenerada e concluída | Aproveitável |
| P03 | Requisitos de software | Bloqueada, regenerada e concluída | Aproveitável |
| P04 | Estruturas de dados | Concluída | Aproveitável |
| P05 | Paradigmas de aprendizado | Concluída | Aproveitável |

- Conclusão: 5/5.
- Históricos conformes: 5/5.
- Questões aproveitáveis na triagem assistida: 5/5.
- Questões aprovadas definitivamente por professores: 0/5 (avaliação ainda não realizada).
- Tempos: P01 2,414 s; P02 4,559 s; P03 4,105 s; P04 2,228 s; P05 1,930 s.
- Mediana: 2,414 s.

## Evidência de recuperação

P02 inicialmente perguntava genericamente qual protocolo deveria ser escolhido. A red flag `selecao_de_protocolo_potencialmente_ambigua` bloqueou o núcleo. A regeneração passou a perguntar pelas garantias indispensáveis, resultando em “entrega confiável e ordenada” como única resposta sustentada.

P03 inicialmente restringia a classificação a um espaço binário inadequado ao formato de cinco alternativas. A red flag `espaco_de_respostas_binario` provocou regeneração; o item final apresentou quatro requisitos e somente o requisito II como restrição de desempenho.

P05 utilizou a família conceitual curada de paradigmas, mantendo alternativas paralelas e evitando “clusterização” como segunda resposta correta.

## Conclusão permitida

Na amostra piloto e após as correções orientadas pelos casos observados, a configuração C4 concluiu cinco questões com históricos conformes e sem defeitos identificados pela triagem semântica assistida. O resultado demonstra viabilidade e capacidade de recuperação para esses casos. Ele não demonstra generalização para temas não cobertos, superioridade sobre C1–C3, validade pedagógica ou validade psicométrica.

## Próximas evidências necessárias

1. avaliação cega por professores;
2. execução das condições C1, C2 e C3;
3. ampliação da amostra para conceitos fora das famílias curadas;
4. aplicação das questões a estudantes para análise psicométrica, se estiver no escopo da pesquisa.
