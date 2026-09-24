# Ablação controlada HAILA

| Condição | n | Aceitáveis | Inconclusivas | Inaceitáveis | IWF médio |
|---|---:|---:|---:|---:|---:|
| C1_LLM | 5 | 3 | 0 | 2 | 1.20 |
| C2_RAG_LLM | 5 | 4 | 0 | 1 | 0.60 |
| C3_RAG_LLM_SLM | 5 | 4 | 0 | 1 | 0.80 |
| C4_HAILA_COMPLETA | 5 | 3 | 0 | 2 | 1.20 |

Pendentes: 0.

> Estudo exploratório com cinco especificações pareadas por condição.


## Uso estimado de tokens remotos

| Condição | Chamadas | Entrada | Saída | Total | Média/questão |
|---|---:|---:|---:|---:|---:|
| C1 — LLM | 5 | 1743 | 1806 | 3549 | 709.8 |
| C2 — RAG + LLM | 5 | 3958 | 1709 | 5667 | 1133.4 |
| C3 — RAG + LLM + SLM | 5 | 8278 | 983 | 9261 | 1852.2 |
| C4 — HAILA completa | 6 | 10086 | 1215 | 11301 | 2260.2 |

> Estimativa com tokenizer proxy Qwen 2.5; as execuções originais não persistiram o campo usage da Groq. Tokens do SLM local não representam cobrança de API. A instrumentação exata foi adicionada para novas rodadas.

## Por que usar a arquitetura modular

Na comparação direta com a LLM isolada, a condição RAG + LLM + SLM elevou a aceitação de 60% para 80%, reduziu os itens inaceitáveis de dois para um e reduziu o IWF médio de 1,20 para 0,80. A SLM também deslocou a geração dos distratores para execução local: os tokens de saída remotos estimados caíram de 1.806 em C1 para 983 em C3, embora o contexto e as instruções maiores tenham elevado o total remoto e a latência.

O RAG apresentou o melhor equilíbrio neste piloto: 80% de aceitação, IWF médio de 0,60 e tempo médio de 2,39 segundos. Isso indica que a fundamentação recuperada responde por parte relevante do ganho observado. A SLM não elevou a taxa de aceitação além de C2, mas acrescentou separação de responsabilidades, controle local sobre os distratores e independência parcial do provedor externo.

A HAILA completa acrescentou governança do processo: registra referência, núcleo, distratores, versões, transições de estado e red flags, além de permitir bloqueio e regeneração. Em P04, três red flags provocaram nova geração antes da conclusão, e a versão final foi classificada como aceitável e sem IWF. Entretanto, P02 e P03 mostraram que as regras determinísticas atuais ainda não cobrem adequadamente ambiguidade semântica e múltiplas respostas defensáveis. Por isso, o resultado atual sustenta superioridade em rastreabilidade e controle, mas não superioridade geral de qualidade.

A conclusão adequada é que a arquitetura modular oferece propriedades que uma LLM monolítica não fornece: grounding explícito, especialização local dos distratores, proveniência por componente, bloqueio determinístico e regeneração auditável. Esses benefícios têm custo de tokens e latência e dependem do aperfeiçoamento contínuo do catálogo de red flags.
