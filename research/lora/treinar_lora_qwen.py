"""Ajusta o Qwen2.5-1.5B-Instruct com LoRA para gerar distratores na HAILA.

Uso (GPU recomendada; uma T4 de 16 GB do Colab é suficiente):

    python research/lora/treinar_lora_qwen.py dados/haila-lora-enade-poscomp adapters/qwen-distratores-lora-v1

Decisões de projeto:
- O prompt de treino é o mesmo da inferência (template de chat do Qwen com
  SYSTEM_DISTRACTORES_QWEN e criar_prompt_distratores), gerado em preparar_dados.py.
- A perda é calculada somente sobre a resposta (o JSON de distratores); os tokens
  do prompt recebem rótulo -100.
- Ao final, o adapter é avaliado no conjunto de validação com as mesmas métricas
  automáticas usadas na dissertação: JSON válido, 4 distratores distintos, cópia do
  gabarito e razão de extensão gabarito/mediana dos distratores.
- treino_config.json registra hiperparâmetros, semente, versões e hashes dos dados,
  para a proveniência do adapter.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import statistics
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from avaliacao_slm import avaliar_validacao  # noqa: E402


def ler_jsonl(caminho: Path) -> list[dict]:
    return [json.loads(l) for l in caminho.read_text(encoding="utf-8").splitlines() if l.strip()]


def sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def montar_exemplo(tokenizer, ex: dict, max_len: int) -> dict | None:
    """Tokeniza prompt e resposta, mascarando o prompt na perda."""
    mensagens = [{"role": "system", "content": ex["system"]}, {"role": "user", "content": ex["prompt"]}]
    prompt_txt = tokenizer.apply_chat_template(mensagens, tokenize=False, add_generation_prompt=True)
    completo_txt = tokenizer.apply_chat_template(
        mensagens + [{"role": "assistant", "content": ex["completion"]}], tokenize=False
    )
    if not completo_txt.startswith(prompt_txt):
        raise ValueError("o template de chat não preserva o prompt como prefixo; verifique o tokenizer")
    prompt_ids = tokenizer(prompt_txt, add_special_tokens=False)["input_ids"]
    completo_ids = tokenizer(completo_txt, add_special_tokens=False)["input_ids"]
    if len(completo_ids) > max_len:
        return None
    labels = [-100] * len(prompt_ids) + completo_ids[len(prompt_ids):]
    return {"input_ids": completo_ids, "attention_mask": [1] * len(completo_ids), "labels": labels}


class Colador:
    def __init__(self, pad_id: int):
        self.pad_id = pad_id

    def __call__(self, lote):
        import torch

        n = max(len(x["input_ids"]) for x in lote)
        def pad(chave, valor):
            return torch.tensor([x[chave] + [valor] * (n - len(x[chave])) for x in lote])
        return {"input_ids": pad("input_ids", self.pad_id), "attention_mask": pad("attention_mask", 0),
                "labels": pad("labels", -100)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dados", type=Path, help="diretório com treino.jsonl e validacao.jsonl")
    ap.add_argument("saida", type=Path, help="diretório do adapter (use em HAILA_SLM_ADAPTER_PATH)")
    ap.add_argument("--modelo-base", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--epocas", type=float, default=3)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--lote", type=int, default=1)
    ap.add_argument("--acumulacao", type=int, default=16)
    ap.add_argument("--r", type=int, default=16)
    ap.add_argument("--alpha", type=int, default=32)
    ap.add_argument("--dropout", type=float, default=0.05)
    ap.add_argument("--max-len", type=int, default=1024)
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--avaliar-max", type=int, default=100, help="itens de validação para a avaliação gerativa")
    ap.add_argument("--teste-rapido", action="store_true",
                    help="usa 16 exemplos e 5 passos, só para conferir que o ambiente funciona")
    args = ap.parse_args()

    import peft
    import torch
    import transformers
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments, set_seed

    set_seed(args.semente)
    treino_bruto = ler_jsonl(args.dados / "treino.jsonl")
    val_bruto = ler_jsonl(args.dados / "validacao.jsonl")
    if args.teste_rapido:
        treino_bruto, val_bruto, args.avaliar_max = treino_bruto[:16], val_bruto[:4], 2
    if not treino_bruto or not val_bruto:
        raise SystemExit("treino.jsonl e validacao.jsonl precisam ter exemplos")

    tokenizer = AutoTokenizer.from_pretrained(args.modelo_base, use_fast=True)
    tokenizer.pad_token = tokenizer.pad_token or tokenizer.eos_token
    treino = [e for e in (montar_exemplo(tokenizer, x, args.max_len) for x in treino_bruto) if e]
    val = [e for e in (montar_exemplo(tokenizer, x, args.max_len) for x in val_bruto) if e]
    print(f"exemplos: treino={len(treino)} validacao={len(val)} "
          f"(descartados por tamanho: {len(treino_bruto) - len(treino) + len(val_bruto) - len(val)})")

    cuda = torch.cuda.is_available()
    mps = not cuda and getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available()
    bf16 = cuda and torch.cuda.is_bf16_supported()
    dispositivo = "cuda" if cuda else ("mps" if mps else "cpu")
    print(f"dispositivo: {dispositivo}" + ("  (sem GPU: o treino completo pode levar muitas horas)" if dispositivo == "cpu" else ""))
    model = AutoModelForCausalLM.from_pretrained(
        args.modelo_base, torch_dtype=torch.bfloat16 if bf16 else torch.float32
    )
    model.config.use_cache = False
    if True:  # checkpointing de gradiente sempre: cabe na T4 (15 GB)
        # Sem GPU, o checkpointing de gradiente reduz o uso de memória; com LoRA
        # ele exige que as entradas propaguem gradiente.
        model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(
        r=args.r, lora_alpha=args.alpha, lora_dropout=args.dropout, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    ))
    model.print_trainable_parameters()

    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(args.saida / "checkpoints"), num_train_epochs=args.epocas, learning_rate=args.lr,
            per_device_train_batch_size=args.lote, per_device_eval_batch_size=args.lote,
            gradient_accumulation_steps=args.acumulacao, lr_scheduler_type="cosine", warmup_ratio=0.05,
            weight_decay=0.0, logging_steps=10, eval_strategy="epoch", save_strategy="epoch",
            save_total_limit=2, load_best_model_at_end=True, metric_for_best_model="eval_loss",
            greater_is_better=False, bf16=bf16, fp16=cuda and not bf16, seed=args.semente,
            max_steps=5 if args.teste_rapido else -1, gradient_checkpointing=True,
            report_to=[], remove_unused_columns=False,
        ),
        train_dataset=treino, eval_dataset=val, data_collator=Colador(tokenizer.pad_token_id),
    )
    inicio = time.time()
    trainer.train()
    duracao = time.time() - inicio
    metricas_eval = trainer.evaluate()

    args.saida.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(args.saida))
    tokenizer.save_pretrained(str(args.saida))

    model.config.use_cache = True
    validacao = avaliar_validacao(model, tokenizer, val_bruto, args.avaliar_max, max_new_tokens=512)
    (args.saida / "relatorio_validacao.json").write_text(
        json.dumps(validacao, ensure_ascii=False, indent=2), encoding="utf-8")

    config = {
        "modelo_base": args.modelo_base,
        "hiperparametros": {k: v for k, v in vars(args).items() if k not in {"dados", "saida", "modelo_base"}},
        "dados": {
            "diretorio": str(args.dados),
            "treino_sha256": sha256(args.dados / "treino.jsonl"),
            "validacao_sha256": sha256(args.dados / "validacao.jsonl"),
            "exemplos_treino": len(treino), "exemplos_validacao": len(val),
        },
        "resultado": {
            "eval_loss": metricas_eval.get("eval_loss"), "duracao_segundos": round(duracao, 1),
            "validacao_gerativa": {k: v for k, v in validacao.items() if k != "por_item"},
        },
        "ambiente": {
            "python": platform.python_version(), "torch": torch.__version__,
            "transformers": transformers.__version__, "peft": peft.__version__,
            "dispositivo": dispositivo, "gpu": torch.cuda.get_device_name(0) if cuda else None,
            "teste_rapido": args.teste_rapido,
        },
    }
    (args.saida / "treino_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(config, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
