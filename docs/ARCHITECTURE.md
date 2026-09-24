# Arquitetura da HAILA

## Camadas operacionais

1. **Frontend** recebe a intenção pedagógica, exibe rastreabilidade e registra o parecer humano.
2. **API** valida entradas e expõe solicitações, geração, histórico e avaliações humanas.
3. **Orquestrador** controla estados, tentativas e o destino de cada regeneração.
4. **RAG** seleciona uma referência relevante de um corpus local auditável.
5. **LLM** gera somente o núcleo: enunciado, gabarito, explicação e metadados pedagógicos.
6. **SLM** gera os quatro distratores; o backend seleciona candidatos sem reescrevê-los.
7. **Validação determinística** aplica regras reproduzíveis antes de liberar uma candidata.
8. **Persistência** registra solicitações, versões, artefatos, proveniência, eventos, red flags e pareceres.

## Fronteira entre sistema e pesquisa

O backend não usa uma segunda LLM para aprovar questões. Avaliação automática por modelos externos pode ser executada em estudos comparativos, mas não altera o estado de produção nem substitui o professor. Essa separação evita apresentar opinião probabilística como red flag determinística.

## Estados principais

`REQUESTED → REFERENCE_RETRIEVED → STEM_GENERATED → DISTRACTORS_GENERATED → ITEM_ASSEMBLED → GENERATION_COMPLETED`

Uma falha verificável leva a `BLOCKED_BY_RED_FLAGS` e à regeneração do núcleo ou dos distratores. O esgotamento dos limites leva a `ATTEMPTS_EXHAUSTED`.

## Correspondência com a figura da dissertação

Na figura anterior, o bloco “Júri” deve ser separado do pipeline. O fluxo operacional termina em “Candidata à revisão humana”. “Juízes LLM” e “Agregação” pertencem ao protocolo experimental de avaliação. O “Catálogo de Red Flags” alimenta regras determinísticas e não participa de votação.
