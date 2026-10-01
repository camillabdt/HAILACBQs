# Avaliação da máquina de estados da HAILA

Executada em: 2026-09-25T15:20:59.304977+00:00

## Fundamentação

A máquina de estados é avaliada como modelo comportamental da arquitetura. Os testes verificam completude do grafo, alcançabilidade, terminação, rejeição de transições inválidas e conformidade dos históricos persistidos.

## Verificações do modelo

- PASSOU - **todos_estados_possuem_regra**: definidos=9, origens=9
- PASSOU - **destinos_sao_estados_validos**: destinos_desconhecidos=[]
- PASSOU - **terminais_sem_saida**: GENERATION_COMPLETED, ATTEMPTS_EXHAUSTED, GENERATION_FAILED
- PASSOU - **todos_estados_alcancaveis**: inalcancáveis=[]
- PASSOU - **repositorio_rejeita_transicao_invalida**: transição inválida: REQUESTED->GENERATION_COMPLETED

## Histórico real

- Solicitações auditadas: 67
- Gerações concluídas: 37
- Históricos conformes: 67 de 67

### Estados observados

- ATTEMPTS_EXHAUSTED: 11
- GENERATION_COMPLETED: 37
- GENERATION_FAILED: 17
- STEM_GENERATED: 2

### Solicitações com problemas

Nenhuma inconformidade encontrada nos históricos disponíveis.

## Limite da conclusão

Conformidade com a máquina de estados demonstra controle do fluxo e rastreabilidade. Ela não demonstra correção conceitual, qualidade pedagógica ou validade psicométrica das questões.
