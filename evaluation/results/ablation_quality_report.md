# Estudo de ablação da HAILA

## Resultados

| Condição | Avaliadas | Aceitáveis | Inconclusivas | Inaceitáveis | Taxa de aceitação | IWF médio |
|---|---:|---:|---:|---:|---:|---:|
| C1_LLM | 5 | 3 | 1 | 1 | 60.0% | 1.00 |
| C2_RAG_LLM | 5 | 1 | 2 | 2 | 20.0% | 1.60 |
| C3_RAG_LLM_SLM | 5 | 3 | 1 | 1 | 60.0% | 1.00 |
| C4_HAILA_COMPLETA | 5 | 4 | 0 | 1 | 80.0% | 1.60 |

## Resultados por item

| Item | C1 | C2 | C3 | C4 |
|---|---:|---:|---:|---:|
| P01 | 1 (A) | 1 (U) | 3 (I) | 1 (A) |
| P02 | 2 (I) | 1 (U) | 0 (A) | 1 (A) |
| P03 | 1 (U) | 3 (I) | 1 (A) | 1 (A) |
| P04 | 1 (A) | 1 (A) | 0 (U) | 4 (I) |
| P05 | 0 (A) | 2 (I) | 1 (A) | 1 (A) |

> A = aceitável; U = inconclusivo por critérios semânticos não resolvidos; I = inaceitável. A regra SAQUET classifica como aceitável apenas o item com todos os critérios resolvidos e no máximo um IWF.

> A avaliação automática é uma triagem e não substitui validação por especialistas.
