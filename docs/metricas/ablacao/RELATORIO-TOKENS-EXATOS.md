# Uso de tokens no experimento de ablação da HAILA

## Escopo da medição

Os valores abaixo são os contadores devolvidos pelos próprios modelos e persistidos
nos artefatos da execução. Para a análise de custo externo, contam-se somente os
tokens enviados à Groq. Os tokens da SLM Qwen são apresentados separadamente porque
o modelo é executado localmente e não gera cobrança de API.

Cada condição contém cinco especificações equivalentes (P01 a P05). Reexecuções de
C1 e C2 foram deduplicadas, mantendo-se uma execução concluída por especificação. Em
C4, as tentativas internas permanecem contabilizadas porque cada chamada remota foi
efetivamente realizada.

| Condição | Concluídas | Groq entrada | Groq saída | Groq total | Média Groq/item | SLM local total |
|---|---:|---:|---:|---:|---:|---:|
| C1 — LLM | 5/5 | 2.438 | 6.106 | 8.544 | 1.708,8 | 0 |
| C2 — RAG + LLM | 5/5 | 4.380 | 5.613 | 9.993 | 1.998,6 | 0 |
| C3 — RAG + LLM + SLM | 5/5 | 4.590 | 3.975 | 8.565 | 1.713,0 | 6.307 |
| C4 — HAILA completa | 2/5 | 10.800 | 8.159 | 18.959 | 3.791,8 | 10.421 |

## Leitura dos resultados

Em comparação com C1, C3 reduziu os tokens de saída pagos de 6.106 para 3.975,
queda de 34,9%. O total de tokens Groq permaneceu praticamente estável: 8.565 em C3
contra 8.544 em C1, aumento de 0,25%. Isso ocorreu porque o RAG acrescentou contexto
à entrada, enquanto a SLM local assumiu a geração dos distratores. Portanto, o ganho
observado nesta amostra é a redução da geração remota e a transferência de trabalho
para processamento local; os dados ainda não sustentam afirmar redução do total de
tokens remotos.

C2 consumiu 16,96% mais tokens Groq que C1. Esse resultado isola o custo de incluir o
contexto recuperado sem transferir a geração dos distratores para a SLM.

C4 não deve ser usada, nesta rodada, como evidência de eficiência: somente duas das
cinco questões chegaram ao estado final e as regenerações elevaram o consumo. O
resultado é útil para diagnosticar o mecanismo de red flags e orientar a redução de
repetições. A comparação de qualidade deve ser apresentada junto com o consumo; esta
tabela, isoladamente, mede eficiência computacional e taxa de conclusão.

## Reprodutibilidade

O arquivo `ablation-cost-exact-summary.json` contém os totais e os valores por questão.
No VS Code, o relatório pode ser recalculado por **Terminal > Executar Tarefa > HAILA:
Consolidar experimento atual**.
