"""Treina e compara as duas versões da SLM em um comando.

    python research/lora/treinar_tudo.py              # treino completo
    python research/lora/treinar_tudo.py --teste-rapido

1. Monta os dados, se ainda não existirem (montar_dataset.py).
2. Treina o LoRA só com ENADE           -> adapters/qwen-distratores-enade
3. Treina o LoRA com ENADE + POSCOMP    -> adapters/qwen-distratores-enade-poscomp
   (ENADE repetido 3x no treino; validação idêntica, só ENADE)
4. Avalia o Qwen base na mesma validação.
5. Gera adapters/comparacao_validacao.md e .json, com a versão recomendada.

Etapas já concluídas (adapter com treino_config.json) são puladas; use --refazer para repetir.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(AQUI))
BASE = "Qwen/Qwen2.5-1.5B-Instruct"
VARIANTES = {
    "enade": ("dados/haila-lora-enade", "adapters/qwen-distratores-enade"),
    "enade-poscomp": ("dados/haila-lora-enade-poscomp", "adapters/qwen-distratores-enade-poscomp"),
}
METRICAS = [
    ("taxa_json_valido", "JSON válido", True), ("taxa_quatro_distintos", "4 distratores distintos", True),
    ("taxa_copia_gabarito", "cópia do gabarito", False), ("mediana_razao_extensao", "razão de extensão (mediana)", None),
    ("taxa_razao_acima_1_5", "gabarito > 1,5× distratores", False),
    ("media_sobreposicao_real", "sobreposição com distratores reais", True),
]


def rodar(*cmd: str) -> None:
    print("\n$", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=RAIZ)


def pontuacao(m: dict) -> tuple:
    """Ordem de prioridade: formato utilizável, sem cópia, extensão homogênea, proximidade."""
    return (round(m["taxa_json_valido"] * m["taxa_quatro_distintos"], 2), -m["taxa_copia_gabarito"],
            -(m["taxa_razao_acima_1_5"] or 1), m["media_sobreposicao_real"] or 0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--teste-rapido", action="store_true")
    ap.add_argument("--refazer", action="store_true")
    args = ap.parse_args()
    py, extra = sys.executable, (["--teste-rapido"] if args.teste_rapido else [])
    sufixo = "-teste" if args.teste_rapido else ""

    if not all((RAIZ / d / "treino.jsonl").exists() for d, _ in VARIANTES.values()):
        rodar(py, str(AQUI / "montar_dataset.py"))

    resultados = {}
    for nome, (dados, adapter) in VARIANTES.items():
        destino = RAIZ / f"{adapter}{sufixo}"
        if args.refazer or not (destino / "treino_config.json").exists():
            rodar(py, str(AQUI / "treinar_lora_qwen.py"), dados, str(destino), *extra)
        cfg = json.loads((destino / "treino_config.json").read_text(encoding="utf-8"))
        resultados[f"lora-{nome}"] = cfg["resultado"]["validacao_gerativa"]

    base_path = RAIZ / f"adapters/qwen-base-validacao{sufixo}.json"
    if args.refazer or not base_path.exists():
        print("\nAvaliando o Qwen base na validação ENADE...", flush=True)
        from avaliacao_slm import avaliar_validacao, carregar
        exemplos = [json.loads(l) for l in (RAIZ / VARIANTES["enade"][0] / "validacao.jsonl")
                    .read_text(encoding="utf-8").splitlines() if l.strip()]
        model, tok = carregar(BASE, None)
        base = avaliar_validacao(model, tok, exemplos, 2 if args.teste_rapido else 1000)
        base_path.parent.mkdir(parents=True, exist_ok=True)
        base_path.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
    base = json.loads(base_path.read_text(encoding="utf-8"))
    resultados = {"qwen-base": {k: v for k, v in base.items() if k != "por_item"}, **resultados}

    melhor = max((k for k in resultados if k.startswith("lora")), key=lambda k: pontuacao(resultados[k]))
    linhas = ["# Comparação na validação ENADE", "",
              f"Itens avaliados: {resultados['qwen-base']['itens']}. Geração determinística (greedy).", "",
              "| Métrica | " + " | ".join(resultados) + " |", "|---|" + "---:|" * len(resultados)]
    for chave, rotulo, _ in METRICAS:
        linhas.append(f"| {rotulo} | " + " | ".join(str(resultados[m].get(chave)) for m in resultados) + " |")
    linhas += ["", f"**Recomendada para o experimento:** `{melhor}` "
               f"(`HAILA_SLM_ADAPTER_PATH={VARIANTES[melhor.removeprefix('lora-')][1]}{sufixo}`).", "",
               "Critério: formato utilizável (JSON válido × 4 distintos), depois menos cópias do gabarito, "
               "depois extensão homogênea, depois proximidade com os distratores reais."]
    (RAIZ / f"adapters/comparacao_validacao{sufixo}.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    (RAIZ / f"adapters/comparacao_validacao{sufixo}.json").write_text(
        json.dumps({"resultados": resultados, "recomendada": melhor}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + "\n".join(linhas))


if __name__ == "__main__":
    main()
