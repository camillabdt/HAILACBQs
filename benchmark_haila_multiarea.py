#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path.home() / "HAILA"
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from haila.iwf import deterministic_iwf

BASE = "http://127.0.0.1:8000"
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")

AREAS = [
    ("banco_dados", [
        ("concorrencia", "Distinguir leitura suja, leitura não repetível e leitura fantasma em um cenário de transações concorrentes.", "Transações, isolamento e controle de concorrência."),
        ("normalizacao", "Analisar dependências funcionais e identificar a forma normal adequada em um esquema relacional.", "Modelagem relacional e normalização."),
    ]),
    ("engenharia_software", [
        ("requisitos", "Classificar corretamente requisitos funcionais e não funcionais a partir de um cenário realista.", "Engenharia de requisitos."),
        ("testes", "Selecionar uma estratégia de teste de software adequada a um defeito ou objetivo de verificação apresentado.", "Teste e qualidade de software."),
    ]),
    ("redes", [
        ("subnetting", "Calcular o prefixo IPv4 adequado para uma necessidade de hosts ou divisão de sub-redes, avaliando somente subnetting.", "Endereçamento IPv4 e subnetting."),
        ("tcp_udp", "Distinguir as garantias de TCP e UDP e selecionar o protocolo adequado a um cenário de comunicação.", "Protocolos de transporte TCP e UDP."),
    ]),
    ("sistemas_operacionais", [
        ("memoria_virtual", "Distinguir tabela de páginas, TLB e estruturas relacionadas à tradução de endereços em memória virtual.", "Memória virtual e paginação."),
        ("escalonamento", "Analisar o comportamento de algoritmos de escalonamento de processos em um cenário simples.", "Escalonamento de CPU."),
    ]),
    ("algoritmos", [
        ("busca_grafos", "Selecionar BFS ou DFS a partir das propriedades do problema e do grafo apresentado.", "Busca em grafos."),
        ("complexidade", "Analisar a complexidade assintótica de um algoritmo ou operação em estrutura de dados.", "Análise de algoritmos e complexidade."),
    ]),
    ("seguranca", [
        ("controle_acesso", "Selecionar o mecanismo de controle de acesso mais adequado para um cenário de autorização.", "Controle de acesso e autorização."),
        ("criptografia", "Distinguir objetivos de hash, criptografia simétrica e criptografia assimétrica em um cenário de segurança.", "Fundamentos de criptografia."),
    ]),
    ("inteligencia_artificial", [
        ("aprendizado", "Distinguir aprendizado supervisionado, não supervisionado e por reforço a partir de um cenário.", "Paradigmas de aprendizado de máquina."),
        ("generalizacao", "Identificar sinais de sobreajuste e selecionar uma ação adequada para melhorar generalização.", "Treinamento, validação e generalização."),
    ]),
    ("sistemas_distribuidos", [
        ("transacoes", "Distinguir 2PC, SAGA e mecanismos relacionados em um cenário de transações distribuídas.", "Transações distribuídas."),
        ("consistencia", "Analisar uma decisão de consistência ou tolerância a falhas em um sistema distribuído.", "Consistência e tolerância a falhas."),
    ]),
    ("arquitetura_computadores", [
        ("cache", "Analisar localidade e comportamento de memória cache em um cenário de acesso.", "Hierarquia de memória e cache."),
        ("desempenho", "Relacionar paralelismo, latência e throughput a uma decisão de arquitetura.", "Desempenho de sistemas computacionais."),
    ]),
    ("linguagens_compiladores", [
        ("compilacao", "Distinguir análise léxica, sintática e semântica durante o processo de compilação.", "Compiladores e análise de programas."),
        ("escopo", "Analisar escopo e vinculação de identificadores em um trecho conceitual de programa.", "Linguagens de programação e escopo."),
    ]),
    ("ihc", [
        ("usabilidade", "Selecionar um princípio de usabilidade adequado diante de um problema de interação.", "Interação humano-computador e usabilidade."),
        ("avaliacao", "Distinguir métodos de avaliação de interface em um cenário de projeto.", "Avaliação de interfaces."),
    ]),
    ("teoria_computacao", [
        ("automatos", "Relacionar autômatos e linguagens formais a uma propriedade de reconhecimento.", "Autômatos e linguagens formais."),
        ("decidibilidade", "Distinguir conceitos de decidibilidade e computabilidade em um cenário conceitual.", "Teoria da computação."),
    ]),
]


def make_tests():
    tests = []
    n = 0
    for area, itens in AREAS:
        for subtema, objetivo, objeto in itens:
            n += 1
            tests.append({
                "nome": f"{area}__{subtema}",
                "area": area,
                "subtema": subtema,
                "payload": {
                    "solicitante_id": f"benchmark-haila-{n:02d}",
                    "curso": "Computação",
                    "exame": "ENADE",
                    "componente": "ESPECIFICO",
                    "objetivo_pedagogico": objetivo,
                    "dificuldade": 3,
                    "competencia": f"Aplicar conhecimentos de {area.replace('_', ' ')} em uma situação-problema.",
                    "habilidade": objetivo,
                    "objeto_conhecimento": objeto,
                    "restricoes": [
                        "Gerar uma questão contextualizada e autocontida.",
                        "Avaliar uma única decisão principal.",
                        "Manter somente uma alternativa defensável como correta.",
                        "Produzir quatro distratores plausíveis e do mesmo nível conceitual do gabarito.",
                        "Evitar pistas lexicais e alternativas absurdas.",
                    ],
                    "max_tentativas": 3,
                    "max_tentativas_distratores": 3,
                },
            })
    return tests


def http_json(method: str, path: str, payload=None, timeout=1200):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        err = RuntimeError(f"HTTP {exc.code}: {json.dumps(parsed, ensure_ascii=False)}")
        err.status = exc.code
        err.retry_after = exc.headers.get("Retry-After")
        raise err from exc


def token_totals(artifacts):
    remote = {"prompt": 0, "completion": 0, "total": 0}
    local = {"input": 0, "output": 0, "total": 0}
    for art in artifacts:
        prov = art.get("provenance") or {}
        ru = prov.get("token_usage_remote") or {}
        lu = prov.get("token_usage_local") or {}
        remote["prompt"] += int(ru.get("prompt_tokens") or 0)
        remote["completion"] += int(ru.get("completion_tokens") or 0)
        remote["total"] += int(ru.get("total_tokens") or 0)
        local["input"] += int(lu.get("input_tokens") or 0)
        local["output"] += int(lu.get("output_tokens") or 0)
        local["total"] += int(lu.get("total_tokens") or 0)
    return remote, local


def route_name(artifacts):
    ds = [a for a in artifacts if a.get("kind") == "DISTRACTORS"]
    if not ds:
        return ""
    model = str((ds[-1].get("provenance") or {}).get("modelo") or "")
    if model.startswith("slm-memory-curated"):
        return "memoria_curada"
    if model.startswith("deterministic-"):
        return "deterministico"
    if "qwen" in model.casefold():
        return "qwen_lora"
    return model or "outro"


def percent(n, d):
    return 0.0 if not d else 100.0 * n / d


def percentile(values, q):
    if not values:
        return 0.0
    xs = sorted(values)
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=12, help="use 24 para o conjunto completo")
    ap.add_argument("--delay", type=float, default=8.0, help="pausa entre questões")
    ap.add_argument("--max-provider-retries", type=int, default=2)
    ap.add_argument("--backoff", type=float, default=30.0)
    ap.add_argument("--input-price-per-million", type=float, default=0.0)
    ap.add_argument("--output-price-per-million", type=float, default=0.0)
    args = ap.parse_args()

    all_tests = make_tests()
    tests = all_tests[: max(1, min(args.limit, len(all_tests)))]
    out = ROOT / "output" / f"benchmark-haila-{STAMP}"
    out.mkdir(parents=True, exist_ok=True)

    _, health = http_json("GET", "/health", timeout=20)
    try:
        _, settings = http_json("GET", "/settings/groq", timeout=20)
    except Exception:
        settings = {}

    print("=" * 78)
    print("HAILA — benchmark multiarea")
    print("=" * 78)
    print("Questões:", len(tests))
    print("Modelo LLM:", settings.get("modelo", "desconhecido"))
    print("SLM:", health.get("slm_base_model"), "| mode:", health.get("slm_mode"))
    print("Saída:", out)

    rows = []
    for idx, test in enumerate(tests, 1):
        print("\n" + "=" * 78)
        print(f"[{idx}/{len(tests)}] {test['nome']}")
        print("=" * 78)

        provider_retries = 0
        provider_wait = 0.0
        attempt_elapsed = 0.0
        rid = None
        generated = None
        history = None
        error = ""

        while provider_retries <= args.max_provider_retries:
            started = time.perf_counter()
            try:
                _, created = http_json("POST", "/requests", test["payload"], timeout=30)
                rid = created["id"]
                _, generated = http_json("POST", f"/requests/{rid}/generate", timeout=1800)
                _, history = http_json("GET", f"/requests/{rid}", timeout=30)
                attempt_elapsed = time.perf_counter() - started
                break
            except Exception as exc:
                attempt_elapsed = time.perf_counter() - started
                if getattr(exc, "status", None) == 429 and provider_retries < args.max_provider_retries:
                    provider_retries += 1
                    try:
                        wait = float(getattr(exc, "retry_after", None))
                    except Exception:
                        wait = args.backoff * provider_retries
                    provider_wait += wait
                    print(f"⚠️ 429; aguardando {wait:.0f}s e recriando a solicitação...")
                    time.sleep(wait)
                    continue
                error = str(exc)
                print("❌", error)
                break

        state = "ERROR" if error else ""
        question = None
        artifacts = []
        historical_flags = []
        req = {}
        final_flags = []

        if history:
            req = history.get("request") or {}
            state = (generated or {}).get("state") or req.get("state") or ""
            latest = history.get("latest_version") or {}
            question = latest.get("question")
            artifacts = history.get("artifacts") or []
            historical_flags = history.get("red_flags") or []
            final_flags = (generated or {}).get("red_flags") or []

        remote, local = token_totals(artifacts)
        route = route_name(artifacts)

        iwf_codes = []
        if question:
            try:
                values = deterministic_iwf(question)
                iwf_codes = [k for k, v in values.items() if v is True]
            except Exception:
                iwf_codes = []

        cost_usd = (
            remote["prompt"] / 1_000_000 * args.input_price_per_million
            + remote["completion"] / 1_000_000 * args.output_price_per_million
        )

        row = {
            "index": idx,
            "nome": test["nome"],
            "area": test["area"],
            "subtema": test["subtema"],
            "request_id": rid or "",
            "state": state,
            "generation_seconds": round(attempt_elapsed, 2),
            "provider_retries": provider_retries,
            "provider_wait_seconds": round(provider_wait, 2),
            "stem_attempts": req.get("stem_attempts", ""),
            "distractor_attempts": req.get("distractor_attempts", ""),
            "historical_red_flags": len(historical_flags),
            "final_red_flags": len(final_flags),
            "route": route,
            "groq_prompt_tokens": remote["prompt"],
            "groq_completion_tokens": remote["completion"],
            "groq_total_tokens": remote["total"],
            "slm_input_tokens": local["input"],
            "slm_output_tokens": local["output"],
            "slm_total_tokens": local["total"],
            "estimated_groq_cost_usd": round(cost_usd, 8),
            "iwf_deterministic_flaws": len(iwf_codes),
            "iwf_flaw_codes": ";".join(iwf_codes),
            "question_generated": bool(question),
            "error": error,
        }
        rows.append(row)

        if history:
            (out / f"{idx:02d}-{test['nome']}.json").write_text(
                json.dumps({
                    "input": test["payload"],
                    "generate_response": generated,
                    "history": history,
                    "metrics": row,
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        print(
            f"{state} | {attempt_elapsed:.2f}s | Groq={remote['total']} tok | "
            f"SLM={local['total']} tok | route={route or '-'} | "
            f"hist_flags={len(historical_flags)} | IWF={len(iwf_codes)}"
        )
        if idx < len(tests) and args.delay > 0:
            time.sleep(args.delay)

    csv_path = out / "resultados.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    (out / "resultados.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    completed = [r for r in rows if r["state"] == "GENERATION_COMPLETED"]
    times = [float(r["generation_seconds"]) for r in completed]
    total_remote = sum(int(r["groq_total_tokens"]) for r in rows)
    total_prompt = sum(int(r["groq_prompt_tokens"]) for r in rows)
    total_completion = sum(int(r["groq_completion_tokens"]) for r in rows)
    total_local = sum(int(r["slm_total_tokens"]) for r in rows)
    total_cost = sum(float(r["estimated_groq_cost_usd"]) for r in rows)
    zero_iwf = sum(int(r["iwf_deterministic_flaws"]) == 0 for r in completed)
    zero_final = sum(int(r["final_red_flags"]) == 0 for r in completed)
    regenerated = sum(
        (int(r["stem_attempts"] or 0) > 1 or int(r["distractor_attempts"] or 0) > 1)
        for r in completed
    )
    routes = Counter(r["route"] for r in completed if r["route"])

    summary = {
        "n": len(rows),
        "completed": len(completed),
        "completion_rate_percent": round(percent(len(completed), len(rows)), 2),
        "median_generation_seconds": round(statistics.median(times), 2) if times else None,
        "p95_generation_seconds": round(percentile(times, 0.95), 2) if times else None,
        "mean_generation_seconds": round(statistics.mean(times), 2) if times else None,
        "zero_final_flags_rate_percent": round(percent(zero_final, len(completed)), 2),
        "zero_deterministic_iwf_flaws_rate_percent": round(percent(zero_iwf, len(completed)), 2),
        "regeneration_rate_percent": round(percent(regenerated, len(completed)), 2),
        "groq_prompt_tokens_total": total_prompt,
        "groq_completion_tokens_total": total_completion,
        "groq_tokens_total": total_remote,
        "groq_tokens_mean_per_completed": round(total_remote / len(completed), 2) if completed else None,
        "slm_tokens_total_observed": total_local,
        "estimated_groq_cost_usd": round(total_cost, 6),
        "routes": dict(routes),
        "model": settings.get("modelo"),
        "slm_model": health.get("slm_base_model"),
        "slm_mode": health.get("slm_mode"),
        "notes": [
            "Tokens vêm da proveniência salva pelo HAILA.",
            "Tokens do SLM representam computação local, não custo de API.",
            "IWF determinístico é proxy de qualidade e não substitui avaliação humana.",
            "Red flags históricas medem pressão de regeneração; final_red_flags mede a resposta retornada.",
        ],
    }

    (out / "resumo.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        "# Benchmark HAILA",
        "",
        f"- Questões: {summary['n']}",
        f"- Concluídas: {summary['completed']} ({summary['completion_rate_percent']}%)",
        f"- Tempo mediano: {summary['median_generation_seconds']} s",
        f"- P95 de tempo: {summary['p95_generation_seconds']} s",
        f"- Sem flags finais: {summary['zero_final_flags_rate_percent']}%",
        f"- Sem falhas IWF determinísticas: {summary['zero_deterministic_iwf_flaws_rate_percent']}%",
        f"- Taxa de regeneração: {summary['regeneration_rate_percent']}%",
        f"- Tokens Groq totais: {summary['groq_tokens_total']}",
        f"- Média de tokens Groq por questão concluída: {summary['groq_tokens_mean_per_completed']}",
        f"- Tokens SLM locais observados: {summary['slm_tokens_total_observed']}",
        f"- Custo Groq estimado: US$ {summary['estimated_groq_cost_usd']}",
        f"- Rotas: {summary['routes']}",
        "",
        "As métricas automáticas demonstram eficiência operacional e conformidade com barreiras de qualidade.",
        "Elas não substituem avaliação humana de correção, plausibilidade e alinhamento pedagógico.",
    ]
    (out / "RELATORIO.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print("\n" + "=" * 78)
    print("RESUMO DO BENCHMARK")
    print("=" * 78)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\nArquivos:")
    print("-", csv_path)
    print("-", out / "resumo.json")
    print("-", out / "RELATORIO.md")


if __name__ == "__main__":
    main()
