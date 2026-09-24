# Experimento comparativo da HAILA

## Pergunta

Qual é a contribuição do RAG, da especialização da geração de distratores e das verificações determinísticas para a qualidade e a confiabilidade do processo de geração de questões?

## Condições

| Código | Condição | Finalidade |
|---|---|---|
| C1 | LLM monolítica, sem RAG | linha de base |
| C2 | LLM monolítica com RAG | efeito da recuperação |
| C3 | RAG + LLM para núcleo + SLM para distratores | efeito da especialização |
| C4 | HAILA completa, incluindo red flags e regeneração | efeito das salvaguardas |

Uma condição só pode receber esse rótulo quando o histórico e a proveniência comprovarem quais componentes foram executados. As quatro questões atualmente persistidas pertencem a C4; portanto, elas não permitem ainda calcular diferenças entre condições.

## Desenho

- Usar o mesmo conjunto congelado de especificações em todas as condições.
- Gerar ao menos cinco questões por condição no piloto (20 no total).
- Alternar a ordem de execução para reduzir efeito de horário, cota e aquecimento.
- Guardar modelo, versão do prompt, semente quando disponível, latência, tentativas, estados, artefatos, red flags e custo.
- Entregar aos avaliadores somente as questões, com códigos aleatórios e sem revelar a condição.
- Aplicar a mesma rubrica humana a todos os itens.

## Desfechos

1. Taxa de conclusão e de bloqueio.
2. Número de tentativas e regenerações.
3. Latência por questão.
4. Sinais determinísticos por questão.
5. Escores humanos de correção, clareza, alinhamento, unicidade do gabarito, distratores e estilo ENADE.
6. Decisão humana: aprovar, corrigir ou rejeitar.

## Análise

Para o piloto, reportar contagens, medianas e distribuição dos escores, sem teste de hipótese. Em uma amostra ampliada, usar comparação pareada por especificação e relatar concordância entre avaliadores. Parecer de LLM, se utilizado, constitui uma camada experimental separada e não o padrão-ouro.
