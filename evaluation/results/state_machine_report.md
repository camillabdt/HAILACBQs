# Avaliação da máquina de estados da HAILA

Executada em: 2026-09-24T13:55:02.135124+00:00

## Fundamentação

A máquina de estados é avaliada como modelo comportamental da arquitetura. Os testes verificam completude do grafo, alcançabilidade, terminação, rejeição de transições inválidas e conformidade dos históricos persistidos.

## Verificações do modelo

- PASSOU - **todos_estados_possuem_regra**: definidos=9, origens=9
- PASSOU - **destinos_sao_estados_validos**: destinos_desconhecidos=[]
- PASSOU - **terminais_sem_saida**: ATTEMPTS_EXHAUSTED, GENERATION_COMPLETED, GENERATION_FAILED
- PASSOU - **todos_estados_alcancaveis**: inalcancáveis=[]
- PASSOU - **repositorio_rejeita_transicao_invalida**: transição inválida: REQUESTED->GENERATION_COMPLETED

## Histórico real

- Solicitações auditadas: 43
- Gerações concluídas: 27
- Históricos conformes: 43 de 43

### Estados observados

- ATTEMPTS_EXHAUSTED: 2
- GENERATION_COMPLETED: 27
- GENERATION_FAILED: 14

### Solicitações com problemas

Nenhuma inconformidade encontrada nos históricos disponíveis.

## Limite da conclusão

Conformidade com a máquina de estados demonstra controle do fluxo e rastreabilidade. Ela não demonstra correção conceitual, qualidade pedagógica ou validade psicométrica das questões.
