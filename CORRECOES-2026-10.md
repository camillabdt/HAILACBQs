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

## Ajuste fino da SLM (LoRA)

- `research/lora/preparar_dados.py`: converte questões reais em exemplos de treino no mesmo
  formato de prompt da inferência, com filtros e relatório de dados.
- `research/lora/treinar_lora_qwen.py`: treino LoRA do Qwen2.5-1.5B-Instruct com perda só na
  resposta, avaliação automática na validação e `treino_config.json` para a proveniência.
- `research/lora/README.md`: passo a passo, incluindo Colab.
- `generator.py`: corrigida a ordem das frases do prompt de sistema do Qwen ("Responda Mantenha
  ... exclusivamente com JSON"); `prompt_version` passou a `qwen-distractors-1.5.0`.
- `api.py`: `/health` informa `slm_mode` (`base` ou `lora`) e se o adapter foi encontrado.
- `tests/test_preparar_dados_lora.py`: 3 testes (30 no total).
- `research/lora/extrair_enade.py`: extrai questões objetivas dos PDFs do INEP (uma ou duas
  colunas), cruza com o gabarito definitivo (PDF ou CSV), ignora anuladas, formação geral e
  discursivas, e gera uma planilha de revisão.
- `research/lora/treinar_no_colab.ipynb`: notebook pronto para o Google Colab (GPU T4).
- `research/lora/coletar_links_enade.js` e `baixar_enade.py`: coleta os links de Computação na página
  do INEP (pelo console do navegador) e baixa os PDFs já renomeados no padrão do extrator.
- Tarefas do VS Code `HAILA LoRA 0` a `HAILA LoRA 4`; suporte a CUDA, MPS e CPU e `--teste-rapido` no treino.
- `extrair_enade.py` validado nas 16 provas reais de Computação (2005–2021): leitura correta dos
  gabaritos, detecção de duas colunas por caractere, letras de alternativa em linha própria, limpeza de
  rodapés e decodificação das provas de 2014 e 2017, cuja fonte Calibri não tem ToUnicode
  (`mapa_calibri_gid.json`, obtido alinhando o texto ao OCR; Courier New pela ordem padrão de glifos).
  Resultado: 353 questões; após `preparar_dados.py`, 97 aceitas (109 no formato I/II/III, 83 com figura).
- `research/lora/importar_geacc.py` e tarefas `HAILA LoRA 0a/0b`: baixam as provas do repositório
  geacc/enade no GitHub e as renomeiam no padrão do extrator.
- `extrair_enade.py`: o início do componente específico é detectado por prova (questão 10 em 2023),
  e a marca d'água de 2023 é removida. Validado também em Redes de Computadores (2014, 2017, 2021)
  e Engenharia de Computação 2019 e 2023. Juntando essas provas às do geacc/enade: 451 questões
  extraídas; 129 aceitas por `preparar_dados.py` (142 no formato I/II/III, 107 com figura).
- `research/lora/converter_poscomp.py`: converte o POSCOMP Dataset (Zenodo 17570916, CC BY 4.0);
  sem Matemática e sem anuladas, 925 questões.
- `preparar_dados.py` aceita várias entradas e informa a contagem por fonte.
- `research/lora/renomear_inep.py`: renomeia os PDFs do INEP pelo nome original.
- `research/lora/montar_dataset.py` + tarefa `HAILA LoRA ★`: monta o conjunto de ponta a ponta com
  fontes fixadas (commit do geacc/enade, md5 do POSCOMP, pdfplumber 0.11.9).
- `research/lora/MANIFESTO_DADOS.json`: hashes e contagens do conjunto usado (777 treino, 128 validação).
- Duas variantes de treino com a mesma validação (26 questões, só ENADE): `haila-lora-enade` (103) e
  `haila-lora-enade-poscomp` (1.085, ENADE repetido 3×). `preparar_dados.py` ganhou `--repetir-enade`.
- `research/lora/avaliacao_slm.py`: métricas de validação compartilhadas, incluindo sobreposição com os
  distratores reais da prova.
- `research/lora/treinar_tudo.py`: treina as duas versões, avalia o Qwen base e gera
  `adapters/comparacao_validacao.md` com a recomendada.
- Treino ajustado para a GPU T4 do Colab (15 GB): lote 1 com acumulação 16 (mesmo lote efetivo de 16),
  checkpointing de gradiente sempre ligado e pesos em fp32 com precisão mista (a T4 não tem bf16).
  Notebook do Colab refeito: acha os arquivos enviados, fixa transformers 4.46.3 / peft 0.13.2 /
  accelerate 1.1.1 e roda tudo com "Executar tudo".
