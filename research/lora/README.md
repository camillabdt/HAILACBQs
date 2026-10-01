# Ajuste fino do Qwen com LoRA para distratores

## Caminho mais curto (terminal)

Na raiz do projeto, com o ambiente ativado (`source .venv/bin/activate`):

```bash
pip install -r backend/requirements.txt
mkdir -p enade/originais          # coloque aqui os PDFs do INEP com o nome original
python research/lora/montar_dataset.py
python research/lora/treinar_tudo.py --teste-rapido
nohup python research/lora/treinar_tudo.py > treino.log 2>&1 &
tail -f treino.log
```

`montar_dataset.py` gera `dados/haila-lora-enade/` (103 treino) e `dados/haila-lora-enade-poscomp/`
(1.085 treino: ENADE repetido 3× + POSCOMP), as duas com a mesma validação de 26 questões do ENADE, e
confere os hashes com `MANIFESTO_DADOS.json`. `treinar_tudo.py` treina as duas versões, avalia o Qwen
base na mesma validação e grava `adapters/comparacao_validacao.md` com a versão recomendada.
Cite o POSCOMP Dataset (DOI 10.5281/zenodo.17570916, CC BY 4.0) na dissertação.

## 0. Caminho manual

1. Abra no navegador a página Provas e Gabaritos do Enade
   (https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/enade/provas-e-gabaritos)
   e clique em cada aba de ano, para o conteúdo carregar.
2. Aperte F12, vá em **Console**, cole o conteúdo de `research/lora/coletar_links_enade.js` e aperte Enter.
   Os links de Ciência da Computação, Engenharia de Computação e Sistemas de Informação são copiados.
3. Crie `enade/links.txt` na raiz do projeto e cole.
4. No VS Code, rode as tarefas `HAILA LoRA 0` a `HAILA LoRA 4` (Terminal > Executar Tarefa).

## 1. Montar as questões de entrada (formato)

Crie um arquivo `questoes.jsonl` com questões objetivas reais (por exemplo, provas do ENADE
de Computação publicadas pelo INEP), uma por linha:

```json
{"id": "enade2021-cc-q12", "enunciado": "...", "alternativas": ["...", "...", "...", "...", "..."], "correta": 2, "fonte": "ENADE 2021 Ciência da Computação", "objeto_conhecimento": "Propriedades ACID e controle de concorrência", "tem_imagem": false}
```

`correta` é o índice da alternativa correta (0 a 4). Use o gabarito definitivo e exclua questões anuladas.
Quanto mais exemplos, melhor; abaixo de ~300 questões aceitas o ajuste tende a ser instável.

## 2. Preparar os dados

```bash
python research/lora/preparar_dados.py questoes.jsonl dados/haila-lora-enade-poscomp
```

O script descarta questões que dependem de figura, formatos fechados (I, II e III; asserção-razão,
que a HAILA trata por regras), duplicatas e itens em que o gabarito tem mais de 1,5 vez a extensão
mediana dos distratores. `relatorio_dados.json` registra quantas questões entraram, por que as
demais saíram e os hashes dos arquivos. Esse relatório entra na Metodologia.

Não use `dados/qwen-enade-curado-v2/` como saída: esse caminho é lido pela memória curada da HAILA.

## 3a. Treinar no VS Code (sua máquina)

Em **Terminal > Executar Tarefa**, rode nesta ordem:

1. `HAILA LoRA 1: Extrair questões do ENADE` (lê `enade/` e grava `dados/questoes.jsonl`)
2. `HAILA LoRA 2: Preparar dados`
3. `HAILA LoRA 3: Teste rápido do treino` (5 passos; confirma que tudo funciona)
4. `HAILA LoRA 4: Treinar`

Antes, instale as dependências no `.venv`: `pip install -r backend/requirements.txt`.
O script detecta sozinho GPU NVIDIA (`cuda`), Mac Apple Silicon (`mps`) ou só CPU. Tempo
aproximado para ~500 questões e 3 épocas: minutos a 1 h em GPU NVIDIA, algumas horas em Mac M1/M2/M3
com 16 GB ou mais, e possivelmente um dia inteiro só em CPU. Se a sua máquina for só CPU, use o Colab.

## 3b. Treinar no Google Colab (GPU T4 ou superior)

```bash
pip install "transformers==4.46.3" "peft==0.13.2" "accelerate==1.1.1"
python research/lora/treinar_lora_qwen.py dados/haila-lora-enade-poscomp adapters/qwen-distratores-lora-v1
```

Hiperparâmetros padrão: r=16, alpha=32, dropout=0,05, taxa de aprendizado 2e-4, 3 épocas,
lote efetivo 16, semente 42, perda somente sobre a resposta. O melhor checkpoint é escolhido
pela perda de validação.

O diretório do adapter recebe:

- os pesos do LoRA e o tokenizer;
- `treino_config.json`: hiperparâmetros, versões, GPU, hashes dos dados e perda final;
- `relatorio_validacao.json`: no conjunto de validação, taxa de JSON válido, taxa de 4 distratores
  distintos, taxa de cópia do gabarito e razão de extensão gabarito/distratores.

## 4. Usar na HAILA

No `.env`:

```
HAILA_SLM_BACKEND=qwen
HAILA_SLM_BASE_MODEL=Qwen/Qwen2.5-1.5B-Instruct
HAILA_SLM_ADAPTER_PATH=adapters/qwen-distratores-lora-v1
```

Confira em `GET /health` que `slm_mode` é `lora` e `slm_adapter_loaded` é `true`. A proveniência de
cada conjunto de distratores passa a registrar `...+LoRA:qwen-distratores-lora-v1`, e
`evaluation/count_distractor_sources.py` contabiliza como `slm_ajustada`.

## Cuidados experimentais

- Congele o adapter (e anote o hash de `treino.jsonl`) antes de rodar o experimento oficial.
- Para que a C4 meça a SLM ajustada, rode-a com `HAILA_USE_CURATED_MEMORY=0`; caso contrário,
  parte dos distratores pode vir da memória curada.
- Compare também com o Qwen base nas mesmas especificações: é isso que mostra o efeito do ajuste.
