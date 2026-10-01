"""Avaliação automática de um gerador de distratores no conjunto de validação (só ENADE).

Métricas por item, agregadas no relatório:
- json_valido: a saída pôde ser interpretada;
- quatro_distintos: exatamente 4 distratores, todos diferentes;
- copia_gabarito: algum distrator é o próprio gabarito;
- razao_extensao: palavras do gabarito / mediana das palavras dos distratores
  (acima de 1,5 o gabarito se destaca pelo tamanho);
- sobreposicao_real: para cada distrator gerado, maior F1 de palavras contra os
  distratores originais da prova; média por item. Mede proximidade com o que
  os elaboradores do ENADE escreveram, não "acerto" (outros distratores podem
  ser igualmente bons).
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))


def palavras(t: str) -> list[str]:
    return re.findall(r"\w+", str(t).casefold())


def f1(a: str, b: str) -> float:
    pa, pb = Counter(palavras(a)), Counter(palavras(b))
    comum = sum((pa & pb).values())
    if not comum:
        return 0.0
    p, r = comum / sum(pa.values()), comum / sum(pb.values())
    return 2 * p * r / (p + r)


def chave(t: str) -> str:
    return re.sub(r"\W+", "", str(t).casefold())


def medir(resposta: str, gerados: list[str] | None, reais: list[str]) -> dict:
    r = {"json_valido": gerados is not None, "quatro_distintos": False, "copia_gabarito": False,
         "razao_extensao": None, "sobreposicao_real": None}
    if not gerados:
        return r
    r["quatro_distintos"] = len(gerados) == 4 and len({chave(t) for t in gerados}) == 4
    r["copia_gabarito"] = chave(resposta) in {chave(t) for t in gerados}
    med = statistics.median(len(palavras(t)) for t in gerados) or 1
    r["razao_extensao"] = round(len(palavras(resposta)) / med, 3)
    r["sobreposicao_real"] = round(statistics.mean(max(f1(g, x) for x in reais) for g in gerados), 3)
    return r


def agregar(resultados: list[dict]) -> dict:
    n = len(resultados) or 1
    razoes = [r["razao_extensao"] for r in resultados if r["razao_extensao"] is not None]
    sobre = [r["sobreposicao_real"] for r in resultados if r["sobreposicao_real"] is not None]
    return {
        "itens": len(resultados),
        "taxa_json_valido": round(sum(r["json_valido"] for r in resultados) / n, 3),
        "taxa_quatro_distintos": round(sum(r["quatro_distintos"] for r in resultados) / n, 3),
        "taxa_copia_gabarito": round(sum(r["copia_gabarito"] for r in resultados) / n, 3),
        "mediana_razao_extensao": round(statistics.median(razoes), 3) if razoes else None,
        "taxa_razao_acima_1_5": round(sum(x > 1.5 for x in razoes) / len(razoes), 3) if razoes else None,
        "media_sobreposicao_real": round(statistics.mean(sobre), 3) if sobre else None,
    }


def avaliar_validacao(model, tokenizer, exemplos: list[dict], limite: int, max_new_tokens: int = 512) -> dict:
    import torch
    from haila.generator import _extrair_json, normalizar_distratores_parciais

    model.eval()
    resultados = []
    for ex in exemplos[:limite]:
        resposta = re.search(r"### Resposta correta:\s*\n(.*?)\n\s*\n", ex["prompt"], re.S).group(1).strip()
        reais = json.loads(ex["completion"])["distratores"]
        msgs = [{"role": "system", "content": ex["system"]}, {"role": "user", "content": ex["prompt"]}]
        texto = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        entrada = tokenizer(texto, return_tensors="pt").to(model.device)
        with torch.inference_mode():
            ids = model.generate(**entrada, max_new_tokens=max_new_tokens, do_sample=False,
                                 pad_token_id=tokenizer.eos_token_id)
        bruto = tokenizer.decode(ids[0][entrada["input_ids"].shape[1]:], skip_special_tokens=True)
        try:
            gerados = [d.texto for d in normalizar_distratores_parciais(_extrair_json(bruto))[0]]
        except ValueError:
            gerados = None
        r = medir(resposta, gerados, reais)
        r.update(id=ex["id"], gerados=gerados, saida=bruto[:400])
        resultados.append(r)
    return dict(agregar(resultados), por_item=resultados)


def carregar(modelo_base: str, adapter: str | None):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(adapter or modelo_base, use_fast=True)
    tok.pad_token = tok.pad_token or tok.eos_token
    dispositivo = "cuda" if torch.cuda.is_available() else (
        "mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else "cpu")
    dtype = torch.bfloat16 if dispositivo == "cuda" and torch.cuda.is_bf16_supported() else (
        torch.float16 if dispositivo == "cuda" else torch.float32)
    model = AutoModelForCausalLM.from_pretrained(modelo_base, torch_dtype=dtype).to(dispositivo)
    if adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter).merge_and_unload()
    return model, tok
