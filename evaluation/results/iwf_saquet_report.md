# Avaliação automática das questões finais — IWF/SAQUET + Arif et al.

> Este resultado combina regras e um juiz LLM. Ele é evidência automática e não substitui professores nem dados de resposta de estudantes.

## Método

Foram aplicados os 19 Item-Writing Flaws (IWF) utilizados pelo SAQUET. Seguindo o limiar apresentado por Moore et al., itens com zero ou uma falha foram classificados como aceitáveis para uso formativo; itens com duas ou mais foram classificados como não aceitáveis. Em paralelo, foram aplicadas as métricas de Arif et al. para relevância, gramática, respondibilidade, clareza, dependência contextual, coerência entre enunciado e opções, homogeneidade e plausibilidade dos distratores.

## Resultado

| Item | IWFs | Classificação | Falhas identificadas | Métricas de Arif |
|---|---:|---|---|---|
| P01 | 1 | acceptable | absolute_terms | 8/8 |
| P02 | 1 | acceptable | absolute_terms | 8/8 |
| P03 | 1 | acceptable | complex_k_type | 8/8 |
| P04 | 4 | unacceptable | implausible_distractors, absolute_terms, convergence_cues, word_repeats | 8/8 |
| P05 | 1 | acceptable | implausible_distractors | 8/8 |

- Itens classificados como aceitáveis: 4/5.
- Itens classificados como não aceitáveis: 1/5.

## Evidências por item

### P01

- **absolute_terms:** regra determinística

### P02

- **absolute_terms:** regra determinística

### P03

- **complex_k_type:** regra determinística

### P04

- **implausible_distractors:** Opções como Heap, Pilha, Tabela hash e Árvore binária de busca são claramente inadequadas para uma fila FIFO, tornando‑as implausíveis.
- **absolute_terms:** regra determinística
- **convergence_cues:** A palavra "fila" aparece no enunciado, coincidindo exatamente com a alternativa correta.
- **word_repeats:** regra determinística

### P05

- **implausible_distractors:** Options like "Aprendizado por reforço" are clearly unrelated to clustering without labels, making them implausible.

## Distribuição das falhas

- absolute_terms: 3/5
- implausible_distractors: 2/5
- complex_k_type: 1/5
- convergence_cues: 1/5
- word_repeats: 1/5

## Interpretação

P01, P02, P03 e P05 atenderam ao limiar automático de aceitabilidade. P04 foi rejeitada porque o próprio enunciado repete “fila”, revelando o gabarito, e porque as demais estruturas são pouco plausíveis no cenário. O resultado é mais rigoroso que a triagem assistida anterior e mostra que conclusão arquitetural não equivale a qualidade do item.

Termos absolutos em P01 e P02 ocorreram em descrições tecnicamente necessárias (por exemplo, ausência de efeitos parciais e entrega de todos os bytes). Por isso, esses sinais devem ser reportados, mas sua gravidade depende do contexto. P03 foi marcado como K-type por usar combinações de itens. P05 permaneceu aceitável, embora o juiz tenha considerado alguns paradigmas pouco plausíveis como distratores.

A ausência de professores limita validade de conteúdo. A ausência de respostas de estudantes impede estimar dificuldade, discriminação e funcionamento dos distratores por medidas psicométricas.
