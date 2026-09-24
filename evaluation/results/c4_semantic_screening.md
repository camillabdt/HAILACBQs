# Triagem semântica da condição C4

**Amostra:** cinco especificações congeladas, uma geração por especificação.  
**Status:** triagem analítica assistida; não substitui o parecer de professores.

## Resultado

| Item | Núcleo | Distratores | Decisão preliminar | Evidência |
|---|---|---|---|---|
| P01 — ACID | Adequado | Inadequados | REJEITAR/REGENERAR | O gabarito “Nenhuma” é sustentado pela explicação, mas os distratores incluem `<NAME>`, “consulta”, “alteração” e “transação”; não formam alternativas conceitualmente paralelas. |
| P02 — TCP/UDP | Adequado | Fracos | CORRIGIR DISTRATORES | UDP é adequado ao cenário. HTTP, SMTP e FTP pertencem à camada de aplicação, tornando a resposta excessivamente evidente e reduzindo a plausibilidade. |
| P03 — requisitos | Adequado | Inadequados | REJEITAR/REGENERAR | O gabarito “Não funcional” está correto, mas “conta”, “transferrencia”, “operacao” e “funcionaria” não são classes alternativas de requisito; há ainda erro ortográfico. |
| P04 — estruturas de dados | Adequado | Inadequados | REJEITAR/REGENERAR | “Fila” atende ao cenário, porém “Lista”, “Linha”, “Arquivo” e “Cola” não constituem quatro confusões plausíveis e paralelas; “Cola” introduz outro idioma/sentido inadequado. |
| P05 — aprendizado | Adequado | Ambíguos | REJEITAR/REGENERAR | “Aprendizado não supervisionado” é correto, mas “Análise de clusterização” também descreve diretamente a tarefa solicitada, criando mais de uma alternativa defensável. |

## Síntese

- Gerações concluídas: 5/5 (100%).
- Históricos conformes à máquina de estados: 5/5 (100%).
- Núcleos considerados adequados nesta triagem: 5/5 (100%).
- Conjuntos de distratores aprováveis sem correção: 0/5 (0%).
- Questões candidatas à aprovação integral: 0/5 (0%).
- Mediana de latência: 31,087 segundos (mínimo 24,353; máximo 31,571).

## Implicação arquitetural

O piloto localiza o principal problema no componente de distratores e na cobertura das red flags. A máquina de estados funcionou como projetada, mas aceitou cinco itens que exigem correção semântica. Assim, a próxima iteração deve fortalecer a SLM, ampliar verificações objetivas e preservar revisão humana para plausibilidade, paralelismo e unicidade do gabarito.
