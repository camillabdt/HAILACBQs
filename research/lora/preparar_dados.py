"""Prepara o conjunto de ajuste fino do Qwen para geração de distratores.

Entrada: um JSONL de questões objetivas reais, uma por linha, no formato

    {"id": "enade2021-q12", "enunciado": "...", "alternativas": ["A", "B", "C", "D", "E"],
     "correta": 2, "fonte": "ENADE 2021", "objeto_conhecimento": "...", "tem_imagem": false}

Saída: treino.jsonl, validacao.jsonl e relatorio_dados.json no diretório indicado.
Cada exemplo usa exatamente o mesmo prompt da inferência da HAILA
(SYSTEM_DISTRACTORES_QWEN + criar_prompt_distratores), para que o modelo seja
ajustado no formato em que será usado.

Uso:
    python research/lora/preparar_dados.py questoes.jsonl dados/haila-lora-v1

Não grave a saída em dados/qwen-enade-curado-v2/: esse é o caminho padrão da
memória curada da HAILA, que passaria a devolver distratores do treino.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
import unicodedata
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))

from haila.generator import SYSTEM_DISTRACTORES_QWEN, criar_prompt_distratores  # noqa: E402
from haila.hybrid import FamiliaQuestao, classificar_familia  # noqa: E402

MARCAS_VISUAIS = re.compile(
    r"\b(figura|imagem|gr[aá]fico|diagrama|tabela (?:a seguir|abaixo|acima)|ilustra[cç][aã]o)\b", re.I
)
CAMINHO_MEMORIA = "dados/qwen-enade-curado-v2"


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\W+", " ", texto.casefold()).strip()


def palavras(texto: str) -> int:
    return len(re.findall(r"\w+", str(texto)))


def avaliar(q: dict, max_razao: float) -> tuple[dict | None, str | None]:
    """Devolve (exemplo, None) se a questão serve para treino, ou (None, motivo)."""
    enunciado = str(q.get("enunciado") or "").strip()
    alternativas = [str(a or "").strip() for a in q.get("alternativas") or []]
    correta = q.get("correta")
    if not enunciado:
        return None, "enunciado_vazio"
    if len(alternativas) != 5 or not all(alternativas):
        return None, "nao_tem_5_alternativas"
    if not isinstance(correta, int) or not 0 <= correta < 5:
        return None, "gabarito_invalido"
    if len({normalizar(a) for a in alternativas}) != 5:
        return None, "alternativas_duplicadas"
    if q.get("tem_imagem") or MARCAS_VISUAIS.search(enunciado):
        return None, "depende_de_recurso_visual"
    resposta = alternativas[correta]
    distratores = [a for i, a in enumerate(alternativas) if i != correta]
    # Formatos fechados (I, II e III; asserção-razão) são tratados por regras
    # determinísticas na HAILA, não pela SLM; treiná-la neles seria inútil.
    familia = classificar_familia(resposta, enunciado)
    if familia in {FamiliaQuestao.COMBINACAO_ITENS, FamiliaQuestao.ASSERCOES}:
        return None, f"formato_fechado_{familia.value}"
    # Mesmo critério proposto para iwf_gabarito_mais_longo: o modelo não deve
    # aprender exemplos em que o gabarito se destaca pela extensão.
    mediana = statistics.median(palavras(d) for d in distratores) or 1
    razao = palavras(resposta) / mediana
    if razao > max_razao:
        return None, "gabarito_destoa_em_extensao"
    exemplo = {
        "id": str(q.get("id") or hashlib.sha256(enunciado.encode()).hexdigest()[:12]),
        "system": SYSTEM_DISTRACTORES_QWEN,
        "prompt": criar_prompt_distratores(enunciado, resposta),
        "completion": json.dumps({"distratores": distratores}, ensure_ascii=False),
        "meta": {
            "fonte": q.get("fonte"),
            "objeto_conhecimento": q.get("objeto_conhecimento"),
            "familia": familia.value,
            "razao_extensao_gabarito": round(razao, 3),
        },
    }
    return exemplo, None


def particao(identificador: str, fracao_validacao: float) -> str:
    """Partição determinística: o mesmo id cai sempre no mesmo conjunto."""
    h = int(hashlib.sha256(identificador.encode()).hexdigest(), 16) % 10_000
    return "validacao" if h < fracao_validacao * 10_000 else "treino"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entrada", type=Path)
    ap.add_argument("saida", type=Path)
    ap.add_argument("--validacao", type=float, default=0.15, help="fração para validação (padrão 0,15)")
    ap.add_argument("--max-razao-extensao", type=float, default=1.5,
                    help="gabarito / mediana dos distratores, em palavras (padrão 1,5)")
    args = ap.parse_args()

    if CAMINHO_MEMORIA in str(args.saida.resolve()).replace("\\", "/"):
        raise SystemExit(f"Escolha outro diretório: {CAMINHO_MEMORIA} é lido pela memória curada da HAILA.")

    descartes, vistos = Counter(), set()
    conjuntos: dict[str, list[dict]] = {"treino": [], "validacao": []}
    linhas = args.entrada.read_text(encoding="utf-8").splitlines()
    for n, linha in enumerate(linhas, 1):
        if not linha.strip():
            continue
        try:
            q = json.loads(linha)
        except json.JSONDecodeError:
            descartes["json_invalido"] += 1
            continue
        chave = normalizar(q.get("enunciado"))
        if chave in vistos:
            descartes["enunciado_repetido"] += 1
            continue
        vistos.add(chave)
        exemplo, motivo = avaliar(q, args.max_razao_extensao)
        if motivo:
            descartes[motivo] += 1
            continue
        conjuntos[particao(exemplo["id"], args.validacao)].append(exemplo)

    args.saida.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for nome, exemplos in conjuntos.items():
        caminho = args.saida / f"{nome}.jsonl"
        caminho.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in exemplos), encoding="utf-8")
        hashes[nome] = hashlib.sha256(caminho.read_bytes()).hexdigest()
    relatorio = {
        "entrada": str(args.entrada),
        "entrada_sha256": hashlib.sha256(args.entrada.read_bytes()).hexdigest(),
        "questoes_lidas": sum(1 for l in linhas if l.strip()),
        "aceitas": {k: len(v) for k, v in conjuntos.items()},
        "descartadas_por_motivo": dict(descartes),
        "criterios": {"max_razao_extensao": args.max_razao_extensao, "fracao_validacao": args.validacao},
        "por_objeto_conhecimento": dict(Counter(
            e["meta"]["objeto_conhecimento"] or "nao_informado" for v in conjuntos.values() for e in v)),
        "sha256": hashes,
    }
    (args.saida / "relatorio_dados.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
