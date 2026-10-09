#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE = "http://127.0.0.1:8000"
ROOT = Path.home() / "HAILA"

TESTES = [
    {
        "area": "Banco de Dados",
        "subtema": "Transações e isolamento",
        "objetivo": "Distinguir anomalias de isolamento em um cenário de transações concorrentes.",
        "competencia": "Analisar mecanismos de controle de concorrência em bancos de dados.",
        "habilidade": "Identificar a anomalia de isolamento a partir de uma situação-problema.",
        "objeto": "Transações, isolamento e controle de concorrência.",
    },
    {
        "area": "Engenharia de Software",
        "subtema": "Engenharia de requisitos",
        "objetivo": "Classificar corretamente requisitos funcionais e não funcionais em um cenário de software.",
        "competencia": "Analisar especificações de requisitos de software.",
        "habilidade": "Classificar requisitos a partir de uma situação-problema.",
        "objeto": "Requisitos funcionais e não funcionais.",
    },
    {
        "area": "Redes de Computadores",
        "subtema": "IPv4 e subnetting",
        "objetivo": "Calcular e selecionar o prefixo IPv4 adequado para uma necessidade de hosts ou subdivisão de rede.",
        "competencia": "Analisar princípios de endereçamento em redes de computadores.",
        "habilidade": "Aplicar CIDR e subnetting em uma situação-problema.",
        "objeto": "Endereçamento IPv4, CIDR e subnetting.",
        "restricoes_extra": [
            "Avaliar somente subnetting; não combinar com roteamento, NAT, DHCP ou VLAN.",
            "O gabarito deve ser apenas um prefixo CIDR (/xx) ou uma máscara decimal IPv4 válida.",
        ],
    },
    {
        "area": "Sistemas Operacionais",
        "subtema": "Memória virtual",
        "objetivo": "Distinguir estruturas e mecanismos de tradução de endereços em memória virtual.",
        "competencia": "Analisar mecanismos de gerenciamento de memória em sistemas operacionais.",
        "habilidade": "Relacionar paginação, tabela de páginas e TLB ao cenário apresentado.",
        "objeto": "Memória virtual, paginação e TLB.",
    },
    {
        "area": "Algoritmos e Estruturas de Dados",
        "subtema": "Busca em grafos",
        "objetivo": "Selecionar a estratégia de busca em grafos adequada às propriedades do problema apresentado.",
        "competencia": "Analisar algoritmos aplicados a estruturas de grafos.",
        "habilidade": "Distinguir busca em largura e busca em profundidade em uma situação-problema.",
        "objeto": "Grafos, BFS e DFS.",
    },
    {
        "area": "Segurança da Informação",
        "subtema": "Criptografia",
        "objetivo": "Distinguir objetivos e usos de hash, criptografia simétrica e criptografia assimétrica.",
        "competencia": "Analisar mecanismos básicos de segurança da informação.",
        "habilidade": "Selecionar o mecanismo criptográfico adequado ao objetivo apresentado.",
        "objeto": "Hash e criptografia simétrica e assimétrica.",
    },
    {
        "area": "Inteligência Artificial",
        "subtema": "Paradigmas de aprendizado",
        "objetivo": "Distinguir aprendizado supervisionado, não supervisionado e por reforço a partir de um cenário.",
        "competencia": "Analisar técnicas fundamentais de inteligência artificial.",
        "habilidade": "Classificar o paradigma de aprendizado adequado ao cenário.",
        "objeto": "Aprendizado supervisionado, não supervisionado e por reforço.",
    },
    {
        "area": "Sistemas Distribuídos",
        "subtema": "Transações distribuídas",
        "objetivo": "Distinguir mecanismos de coordenação de transações distribuídas em um cenário.",
        "competencia": "Analisar mecanismos de consistência e coordenação em sistemas distribuídos.",
        "habilidade": "Relacionar 2PC, SAGA e alternativas de coordenação ao problema apresentado.",
        "objeto": "Transações distribuídas, 2PC e SAGA.",
    },
    {
        "area": "Arquitetura de Computadores",
        "subtema": "Memória cache",
        "objetivo": "Analisar o efeito da localidade de acesso sobre o comportamento da memória cache.",
        "competencia": "Analisar a hierarquia de memória de sistemas computacionais.",
        "habilidade": "Relacionar localidade temporal e espacial ao desempenho de cache.",
        "objeto": "Hierarquia de memória, cache e localidade.",
    },
    {
        "area": "Compiladores e Linguagens",
        "subtema": "Fases de compilação",
        "objetivo": "Distinguir análise léxica, sintática e semântica a partir de um erro ou tarefa de compilação.",
        "competencia": "Analisar etapas do processamento de linguagens de programação.",
        "habilidade": "Relacionar um problema à fase adequada do compilador.",
        "objeto": "Análise léxica, sintática e semântica.",
    },
    {
        "area": "Interação Humano-Computador",
        "subtema": "Usabilidade",
        "objetivo": "Selecionar um princípio de usabilidade adequado diante de um problema de interação.",
        "competencia": "Analisar qualidade de interação em interfaces computacionais.",
        "habilidade": "Relacionar problemas de interface a princípios de usabilidade.",
        "objeto": "Usabilidade e avaliação de interfaces.",
    },
    {
        "area": "Teoria da Computação",
        "subtema": "Autômatos e linguagens",
        "objetivo": "Relacionar modelos de autômatos às classes de linguagens que reconhecem.",
        "competencia": "Analisar fundamentos formais da computação.",
        "habilidade": "Distinguir modelos de reconhecimento de linguagens formais.",
        "objeto": "Autômatos finitos e linguagens formais.",
    },
]


class HttpFailure(RuntimeError):
    def __init__(self, status: int, path: str, body: str, retry_after: str | None = None):
        super().__init__(f"HTTP {status} em {path}: {body}")
        self.status = status
        self.retry_after = retry_after


def http_json(method: str, path: str, payload=None, timeout=1800):
    data = None
    headers = {"Accept": "application/json"}

    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise HttpFailure(
            exc.code,
            path,
            body,
            exc.headers.get("Retry-After"),
        ) from exc


def payload_do_teste(i: int, teste: dict) -> dict:
    restricoes = [
        "Gerar uma questão contextualizada e autocontida.",
        "Avaliar uma única decisão principal.",
        "Manter somente uma alternativa defensável como correta.",
        "Produzir quatro distratores plausíveis e do mesmo nível conceitual do gabarito.",
        "Evitar pistas lexicais, alternativas absurdas e formulações ambíguas.",
    ]
    restricoes.extend(teste.get("restricoes_extra", []))

    return {
        "solicitante_id": f"benchmark-haila-12areas-{i:02d}",
        "curso": "Computação",
        "exame": "ENADE",
        "componente": "ESPECIFICO",
        "objetivo_pedagogico": teste["objetivo"],
        "dificuldade": 3,
        "competencia": teste["competencia"],
        "habilidade": teste["habilidade"],
        "objeto_conhecimento": teste["objeto"],
        "restricoes": restricoes,
        "max_tentativas": 3,
        "max_tentativas_distratores": 3,
    }


def tokens(artifacts):
    groq_in = groq_out = groq_total = 0
    slm_in = slm_out = slm_total = 0

    for art in artifacts:
        prov = art.get("provenance") or {}
        ru = prov.get("token_usage_remote") or {}
        lu = prov.get("token_usage_local") or {}

        groq_in += int(ru.get("prompt_tokens") or 0)
        groq_out += int(ru.get("completion_tokens") or 0)
        groq_total += int(ru.get("total_tokens") or 0)

        slm_in += int(lu.get("input_tokens") or 0)
        slm_out += int(lu.get("output_tokens") or 0)
        slm_total += int(lu.get("total_tokens") or 0)

    return {
        "groq_prompt_tokens": groq_in,
        "groq_completion_tokens": groq_out,
        "groq_total_tokens": groq_total,
        "slm_input_tokens": slm_in,
        "slm_output_tokens": slm_out,
        "slm_total_tokens": slm_total,
    }


def rota(artifacts):
    ds = [a for a in artifacts if a.get("kind") == "DISTRACTORS"]
    if not ds:
        return "", "", ""

    prov = ds[-1].get("provenance") or {}
    model = str(prov.get("modelo") or "")

    if model.startswith("slm-memory-curated"):
        route = "memoria_curada"
    elif model.startswith("deterministic-"):
        route = "deterministico"
    elif "Qwen" in model or "qwen" in model:
        route = "qwen_lora"
    else:
        route = "outro"

    return route, model, str(prov.get("estrategia") or "")


def automatic_checks(question):
    if not question:
        return {
            "q_exists": False,
            "five_alternatives": False,
            "unique_alternatives": False,
            "valid_answer_index": False,
            "auto_structure_pass": False,
        }

    alts = question.get("alternativas") or []
    correta = question.get("correta")
    unique = len({str(x).strip().casefold() for x in alts}) == len(alts)

    valid_idx = (
        isinstance(correta, int)
        and 0 <= correta < len(alts)
    )

    return {
        "q_exists": True,
        "five_alternatives": len(alts) == 5,
        "unique_alternatives": unique,
        "valid_answer_index": valid_idx,
        "auto_structure_pass": (
            len(alts) == 5
            and unique
            and valid_idx
            and bool(str(question.get("enunciado") or "").strip())
            and bool(str(question.get("explicacao") or "").strip())
        ),
    }


def percentile(values, p):
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def safe_mean(xs):
    return statistics.mean(xs) if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=45.0)
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--input-price", type=float, default=0.15)
    ap.add_argument("--output-price", type=float, default=0.60)
    ap.add_argument("--max-429-retries", type=int, default=2)
    args = ap.parse_args()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = ROOT / "output" / f"benchmark-haila-12areas-{stamp}"
    out.mkdir(parents=True, exist_ok=True)

    _, health = http_json("GET", "/health", timeout=20)
    _, settings = http_json("GET", "/settings/groq", timeout=20)

    model = settings.get("modelo")
    if model != "openai/gpt-oss-120b":
        raise SystemExit(
            f"Modelo atual={model!r}. "
            "Para comparação justa, use openai/gpt-oss-120b."
        )

    testes = TESTES[: max(1, min(args.limit, len(TESTES)))]
    rows = []
    human_rows = []

    print("=" * 88)
    print("HAILA — BENCHMARK 12 ÁREAS")
    print("=" * 88)
    print("Modelo LLM:", model)
    print("SLM:", health.get("slm_base_model"), "| modo:", health.get("slm_mode"))
    print("Questões:", len(testes))
    print("Intervalo planejado:", args.delay, "s")
    print("Saída:", out)

    for i, teste in enumerate(testes, 1):
        payload = payload_do_teste(i, teste)

        print("\n" + "=" * 88)
        print(f"[{i}/{len(testes)}] {teste['area']} — {teste['subtema']}")
        print("=" * 88)

        started = time.perf_counter()
        rid = None
        provider_retries = 0
        provider_wait = 0.0
        error = ""
        error_class = ""
        generated = {}
        history = {}

        try:
            _, created = http_json("POST", "/requests", payload, timeout=30)
            rid = created["id"]
            print("Request ID:", rid)

            while True:
                try:
                    _, generated = http_json(
                        "POST",
                        f"/requests/{rid}/generate",
                        timeout=1800,
                    )
                    break
                except HttpFailure as exc:
                    if exc.status == 429 and provider_retries < args.max_429_retries:
                        provider_retries += 1
                        try:
                            wait = float(exc.retry_after)
                        except Exception:
                            wait = 65.0
                        wait = max(wait, 10.0)
                        provider_wait += wait
                        print(
                            f"⚠️ PROVIDER_LIMIT; aguardando {wait:.0f}s "
                            f"(retry {provider_retries}/{args.max_429_retries})"
                        )
                        time.sleep(wait)
                        continue
                    raise

            _, history = http_json("GET", f"/requests/{rid}", timeout=30)

        except HttpFailure as exc:
            error = str(exc)
            error_class = (
                "PROVIDER_LIMIT" if exc.status == 429
                else "BACKEND_HTTP_ERROR"
            )
        except Exception as exc:
            error = str(exc)
            error_class = "ERROR"

        elapsed = time.perf_counter() - started

        req = history.get("request") or {}
        artifacts = history.get("artifacts") or []
        historical_flags = history.get("red_flags") or []
        latest = history.get("latest_version") or {}
        question = latest.get("question")
        final_flags = generated.get("red_flags") or []

        state = (
            generated.get("state")
            or req.get("state")
            or error_class
            or "UNKNOWN"
        )

        tok = tokens(artifacts)
        route, dmodel, strategy = rota(artifacts)
        checks = automatic_checks(question)

        cost = (
            tok["groq_prompt_tokens"] / 1_000_000 * args.input_price
            + tok["groq_completion_tokens"] / 1_000_000 * args.output_price
        )

        operational_success = state == "GENERATION_COMPLETED"
        automatic_quality_pass = (
            operational_success
            and len(final_flags) == 0
            and checks["auto_structure_pass"]
        )

        row = {
            "id": i,
            "area": teste["area"],
            "subtema": teste["subtema"],
            "request_id": rid or "",
            "state": state,
            "operational_success": operational_success,
            "automatic_quality_pass": automatic_quality_pass,
            "duration_seconds": round(elapsed, 2),
            "provider_wait_seconds": round(provider_wait, 2),
            "provider_retries": provider_retries,
            "attempts": req.get("attempts", ""),
            "stem_attempts": req.get("stem_attempts", ""),
            "distractor_attempts": req.get("distractor_attempts", ""),
            "historical_red_flags": len(historical_flags),
            "final_red_flags": len(final_flags),
            "route": route,
            "distractor_model": dmodel,
            "strategy": strategy,
            **tok,
            "estimated_groq_cost_usd": round(cost, 8),
            **checks,
            "error_class": error_class,
            "error": error,
        }
        rows.append(row)

        if question:
            human_rows.append({
                "id": i,
                "area": teste["area"],
                "subtema": teste["subtema"],
                "enunciado": question.get("enunciado", ""),
                "A": (question.get("alternativas") or ["", "", "", "", ""])[0],
                "B": (question.get("alternativas") or ["", "", "", "", ""])[1],
                "C": (question.get("alternativas") or ["", "", "", "", ""])[2],
                "D": (question.get("alternativas") or ["", "", "", "", ""])[3],
                "E": (question.get("alternativas") or ["", "", "", "", ""])[4],
                "gabarito": (
                    chr(65 + question["correta"])
                    if isinstance(question.get("correta"), int)
                    and 0 <= question["correta"] < 5
                    else ""
                ),
                "explicacao": question.get("explicacao", ""),
                "correcao_1a5": "",
                "clareza_1a5": "",
                "alinhamento_1a5": "",
                "distratores_1a5": "",
                "estilo_enade_1a5": "",
                "comentario_avaliador": "",
            })

            (out / f"{i:02d}.json").write_text(
                json.dumps(
                    {
                        "input": payload,
                        "generate_response": generated,
                        "history": history,
                        "metrics": row,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        print(
            f"{state} | {elapsed:.2f}s | route={route or '-'} | "
            f"Groq={tok['groq_total_tokens']} tok | "
            f"US$={cost:.6f} | hist_flags={len(historical_flags)} | "
            f"final_flags={len(final_flags)}"
        )

        if error:
            print("ERRO:", error_class, error)

        if i < len(testes) and args.delay > 0:
            print(f"Aguardando {args.delay:.0f}s...")
            time.sleep(args.delay)

    metrics_csv = out / "metricas.csv"
    with metrics_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    human_csv = out / "avaliacao_humana.csv"
    if human_rows:
        with human_csv.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(human_rows[0].keys()))
            writer.writeheader()
            writer.writerows(human_rows)

    completed = [r for r in rows if r["operational_success"]]
    times = [r["duration_seconds"] for r in completed]
    costs = [r["estimated_groq_cost_usd"] for r in rows]
    routes = Counter(r["route"] for r in completed if r["route"])

    summary = {
        "timestamp": stamp,
        "model": model,
        "slm_model": health.get("slm_base_model"),
        "slm_mode": health.get("slm_mode"),
        "n": len(rows),
        "completed": len(completed),
        "completion_rate_percent": round(100 * len(completed) / len(rows), 2),
        "automatic_quality_pass_count": sum(r["automatic_quality_pass"] for r in rows),
        "automatic_quality_pass_rate_percent": round(
            100 * sum(r["automatic_quality_pass"] for r in rows) / len(rows), 2
        ),
        "mean_seconds_completed": round(safe_mean(times), 2) if times else None,
        "median_seconds_completed": round(statistics.median(times), 2) if times else None,
        "p95_seconds_completed": round(percentile(times, 0.95), 2) if times else None,
        "groq_prompt_tokens_total": sum(r["groq_prompt_tokens"] for r in rows),
        "groq_completion_tokens_total": sum(r["groq_completion_tokens"] for r in rows),
        "groq_tokens_total": sum(r["groq_total_tokens"] for r in rows),
        "slm_tokens_total": sum(r["slm_total_tokens"] for r in rows),
        "estimated_groq_cost_usd_total": round(sum(costs), 6),
        "estimated_groq_cost_usd_mean_per_completed": round(
            sum(costs) / len(completed), 6
        ) if completed else None,
        "provider_limit_events": sum(r["provider_retries"] for r in rows),
        "historical_red_flags_total": sum(r["historical_red_flags"] for r in rows),
        "routes": dict(routes),
        "pricing_used_usd_per_million_tokens": {
            "input": args.input_price,
            "output": args.output_price,
        },
        "quality_note": (
            "automatic_quality_pass mede conclusão, ausência de flags finais e "
            "estrutura básica válida. Não substitui avaliação humana."
        ),
    }

    (out / "resumo.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = f"""# Benchmark HAILA — 12 áreas

## Configuração

- LLM: `{model}`
- SLM: `{health.get("slm_base_model")}`
- Modo SLM: `{health.get("slm_mode")}`
- Questões: {summary["n"]}
- Preço de referência: US$ {args.input_price}/1M tokens de entrada e US$ {args.output_price}/1M tokens de saída.

## Resultados operacionais

- Concluídas: {summary["completed"]}/{summary["n"]} ({summary["completion_rate_percent"]}%)
- Passaram os critérios automáticos: {summary["automatic_quality_pass_count"]}/{summary["n"]} ({summary["automatic_quality_pass_rate_percent"]}%)
- Tempo médio das concluídas: {summary["mean_seconds_completed"]} s
- Mediana: {summary["median_seconds_completed"]} s
- P95: {summary["p95_seconds_completed"]} s
- Tokens Groq totais: {summary["groq_tokens_total"]}
- Tokens SLM locais observados: {summary["slm_tokens_total"]}
- Custo Groq estimado total: US$ {summary["estimated_groq_cost_usd_total"]}
- Custo Groq médio por questão concluída: US$ {summary["estimated_groq_cost_usd_mean_per_completed"]}
- Eventos de limite do provedor tratados: {summary["provider_limit_events"]}
- Red Flags históricas: {summary["historical_red_flags_total"]}
- Rotas finais: {summary["routes"]}

## Interpretação

Os critérios automáticos medem robustez operacional e conformidade estrutural.
A qualidade pedagógica e a correção conceitual devem ser complementadas pela
avaliação humana disponível em `avaliacao_humana.csv`.
"""
    (out / "RELATORIO.md").write_text(report, encoding="utf-8")

    print("\n" + "=" * 88)
    print("RESUMO FINAL")
    print("=" * 88)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\nArquivos gerados:")
    print("-", metrics_csv)
    print("-", human_csv)
    print("-", out / "resumo.json")
    print("-", out / "RELATORIO.md")


if __name__ == "__main__":
    main()
