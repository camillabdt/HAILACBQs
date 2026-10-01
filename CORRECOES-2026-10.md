# Correções de outubro/2026

## Máquina de estados

- `domain.py`: adicionadas as transições `REFERENCE_RETRIEVED → BLOCKED_BY_RED_FLAGS`
  (primeira saída da LLM ininterpretável) e a autotransição explícita
  `BLOCKED_BY_RED_FLAGS → BLOCKED_BY_RED_FLAGS` (falhas de interpretação consecutivas).
  Exposto `ESTADOS_TERMINAIS`.
- `repository.py`: removida a exceção que aceitava qualquer autotransição
  (`to_state != old`). Agora só passam as transições declaradas no modelo.
- `orchestrator.py`: toda exceção não tratada (RAG sem referência, cota da Groq,
  falha ao carregar a SLM) leva a solicitação a `GENERATION_FAILED` antes de ser
  propagada. Antes, a solicitação ficava parada em `REQUESTED` ou `REFERENCE_RETRIEVED`.
- `evaluate_state_machine.py`: o oráculo deixou de aceitar autotransições não
  declaradas e passou a exigir que o estado persistido seja terminal.
- `STATE_MACHINE.md`: diagrama e lista de verificações atualizados.
- `tests/test_state_machine_fixes.py`: quatro testes de regressão (27 testes no total).

Efeito observado: o banco `backend/runtime/haila.sqlite3` tem 5 solicitações paradas em
`REQUESTED`. O verificador antigo as considerava conformes; o novo as aponta.

## Proveniência

- `redflags.py`: `catalog_version` passou a ser uma única fonte (`haila-redflags-3.1.0`);
  antes a classe declarava 3.0.0 e a proveniência gravava 3.1.0.
- `evaluation/count_distractor_sources.py`: conta a origem dos distratores na C4
  (SLM base, SLM ajustada, memória curada ou regra determinística).

Resultado nas execuções existentes:

| Execução | Conjuntos de distratores gerados | Versão final dos concluídos |
|---|---|---|
| oficial-20260925-113346 (P01–P05) | 9 SLM base, 2 memória curada | 1 SLM base, 1 memória curada |
| oficial-expandido-20260925-155245 (E01–E12) | 37 SLM base | 4 SLM base |

Nenhuma execução usou adapter LoRA.

## Não alterado (decisões metodológicas pendentes)

- Limiares das red flags `iwf_gabarito_mais_longo`, `iwf_comando_negativo` e `iwf_termo_absoluto`.
- Diferença de gerador de distratores entre C3 (Qwen puro) e C4 (roteador híbrido).
- Margem de não inferioridade da H3.
