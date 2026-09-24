# Comparação preliminar da melhoria dos distratores

## Desenho

Foram usadas as mesmas cinco especificações congeladas antes e depois da ativação da memória conceitual, das regras de família, da filtragem de placeholders e do reforço do prompt. Cada condição possui uma geração por especificação; os números são descritivos e não sustentam teste de hipótese.

## Resultado

| Medida | Antes | Depois (v2) |
|---|---:|---:|
| Gerações concluídas | 5/5 | 5/5 |
| Núcleos adequados na triagem | 5/5 | 4/5 |
| Conjuntos de distratores aproveitáveis | 0/5 | 3/5 |
| Questões integralmente aproveitáveis | 0/5 | 3/5 |
| Mediana de latência | 31,087 s | 2,319 s |

## Leitura por item da rodada v2

- P01 (ACID): aproveitável; família ACID coerente.
- P02 (TCP/UDP): aproveitável; protocolos comparáveis, embora a dificuldade deva ser confirmada por professor.
- P03 (requisitos): rejeitado; REQ2, REQ3 e REQ4 podem ser requisitos não funcionais.
- P04 (estruturas de dados): aproveitável; estruturas de dados paralelas.
- P05 (aprendizado): rejeitado; após uma red flag, a segunda tentativa abandonou a memória e produziu categorias vagas.

## Conclusão permitida

Nesta amostra pequena, a mudança eliminou os defeitos mais grosseiros em três dos cinco itens e reduziu a mediana de latência porque famílias conhecidas dispensaram inferência local. Persistiram uma falha de unicidade no núcleo e uma falha de recuperação após rejeição. Ambas motivaram novas correções, que exigem outra rodada antes de qualquer conclusão final.
