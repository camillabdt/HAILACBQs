# Avaliação da máquina de estados da HAILA

Executada em: 2026-09-25T22:28:18.483370+00:00

## Fundamentação

A máquina de estados é avaliada como modelo comportamental da arquitetura. Os testes verificam completude do grafo, alcançabilidade, terminação, rejeição de transições inválidas e conformidade dos históricos persistidos.

## Verificações do modelo

- PASSOU - **todos_estados_possuem_regra**: definidos=9, origens=9
- PASSOU - **destinos_sao_estados_validos**: destinos_desconhecidos=[]
- PASSOU - **terminais_sem_saida**: GENERATION_FAILED, GENERATION_COMPLETED, ATTEMPTS_EXHAUSTED
- PASSOU - **todos_estados_alcancaveis**: inalcancáveis=[]
- PASSOU - **repositorio_rejeita_transicao_invalida**: transição inválida: REQUESTED->GENERATION_COMPLETED

## Histórico real

- Solicitações auditadas: 12
- Gerações concluídas: 4
- Históricos conformes: 12 de 12

### Estados observados

- ATTEMPTS_EXHAUSTED: 8
- GENERATION_COMPLETED: 4

### Solicitações com problemas

Nenhuma inconformidade encontrada nos históricos disponíveis.

## Limite da conclusão

Conformidade com a máquina de estados demonstra controle do fluxo e rastreabilidade. Ela não demonstra correção conceitual, qualidade pedagógica ou validade psicométrica das questões.
