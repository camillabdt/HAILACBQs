# Protocolo de avaliação da arquitetura HAILA

A avaliação possui três objetos separados: comportamento arquitetural, contribuição dos componentes e qualidade das questões. Essa separação evita usar uma boa execução como prova de qualidade pedagógica ou uma boa questão isolada como prova da arquitetura.

## 1. Conformidade da máquina de estados

A sugestão do orientador é operacionalizada como teste baseado em modelo. A máquina de estados definida no código funciona como modelo comportamental, do qual derivamos verificações de:

- completude dos estados e das transições;
- alcançabilidade;
- estados terminais sem saída;
- rejeição de transições ilegais;
- conformidade dos históricos reais;
- presença dos artefatos exigidos em uma geração concluída;
- coerência entre último evento e estado persistido.

A inspiração metodológica é o teste baseado em modelos, no qual modelos comportamentais são usados para derivar casos e verificar conformidade (Utting, Pretschner e Legeard, 2012). A escolha de cenários e atributos de qualidade também se aproxima da avaliação arquitetural do ATAM, sem afirmar que este piloto executa um ATAM completo. A máquina de estados não atribui nota pedagógica à questão: ela verifica se o processo executado respeita a arquitetura projetada.

## 2. Estudo de ablação

As mesmas especificações serão executadas nas condições:

1. LLM monolítica, sem RAG;
2. LLM monolítica com RAG;
3. RAG + LLM para núcleo + SLM para distratores;
4. HAILA completa com verificações determinísticas.

As comparações isolam o efeito do RAG, da SLM e das regras. Serão registrados conclusão, falhas, tentativas, regenerações, latência, custo, artefatos e proveniência.

## 3. Avaliação das questões

- SAQUET e MedIWF inspiram a inspeção de falhas de escrita e a comparação posterior com rótulos humanos.
- SBIE orienta dimensões amplas de qualidade.
- ICALT orienta as categorias semânticas RF1-RF8.
- A revisão de AQG de Oliveira et al. fundamenta a combinação de avaliação automática e humana.
- Arif et al. fundamenta manter separadas as avaliações humana, por regras e por LLM.

Pareceres de LLM são resultados experimentais, não verdade de referência. Red flags determinísticas e RF1-RF8 semânticas serão reportadas em camadas distintas.

## 4. Interpretação permitida

O eixo de estados permite concluir sobre controle do fluxo e rastreabilidade. A ablação permite estimar a contribuição dos componentes. As rubricas automáticas caracterizam as saídas. Validade pedagógica e psicométrica exigem evidência humana e, quando aplicável, respostas de estudantes.

## Referências metodológicas adicionais

- UTTING, M.; PRETSCHNER, A.; LEGEARD, B. A taxonomy of model-based testing approaches. Software Testing, Verification and Reliability, v. 22, n. 5, p. 297-312, 2012. DOI: 10.1002/stvr.456.
- SOFTWARE ENGINEERING INSTITUTE. Architecture Tradeoff Analysis Method (ATAM). Carnegie Mellon University.
- PEFFERS, K. et al. A Design Science Research Methodology for Information Systems Research. Journal of Management Information Systems, v. 24, n. 3, p. 45-77, 2007.

Links para conferência:

- Utting, Pretschner e Legeard: https://doi.org/10.1002/stvr.456
- SEI/CMU, ATAM: https://www.sei.cmu.edu/library/architecture-tradeoff-analysis-method-atam/
- Peffers et al., DSRM: https://www.jmis-web.org/articles/765
