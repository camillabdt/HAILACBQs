#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter

import experimento_100_haila_jev_pareado as exp


def latest_successes(rows):
    out = {}
    for row in rows:
        if row.get("state") == "GENERATION_COMPLETED" and row.get("question"):
            out[row["case_id"]] = row
    return out


def latest_jev_ok(rows):
    out = {}
    for row in rows:
        if row.get("status") == "OK":
            out[row["case_id"]] = row
    return out


def export_summary(progress):
    rows = exp.read_jsonl(progress)
    ok_map = latest_jev_ok(rows)
    ok = list(ok_map.values())

    summary = {
        "n_ok_unique": len(ok),
        "mean_latency_ms": (
            statistics.mean(
                float(r["latency_ms"])
                for r in ok
                if r.get("latency_ms") is not None
            )
            if any(r.get("latency_ms") is not None for r in ok)
            else None
        ),
        "total_input_tokens": sum(int(r.get("input_tokens") or 0) for r in ok),
        "total_output_tokens": sum(int(r.get("output_tokens") or 0) for r in ok),
        "total_cost_usd": sum(float(r.get("estimated_cost_usd") or 0) for r in ok),
        "criterion_means": {},
        "lowest_criterion_counts": dict(
            Counter(r.get("lowest_criterion") for r in ok if r.get("lowest_criterion"))
        ),
        "note": (
            "Avaliação Jev em shadow sobre questões baseline já concluídas. "
            "Erros anteriores permanecem no JSONL para auditoria, mas somente status=OK "
            "conta como avaliação concluída."
        ),
    }

    for k in exp.CRITERIA:
        vals = [float(r[k]) for r in ok if r.get(k) is not None]
        summary["criterion_means"][k] = statistics.mean(vals) if vals else None

    (exp.OUT / "jev_resumo_parcial_robusto.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    exp.export_csv(ok, exp.OUT / "jev_metricas_parcial_robusto.csv")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--max-retries", type=int, default=3)
    ap.add_argument("--cooldown", type=float, default=15.0)
    args = ap.parse_args()

    settings = exp.http_json("GET", "/settings/jev", timeout=20)
    if not settings.get("enabled"):
        raise SystemExit(
            "❌ O Jev está desligado. Defina HAILA_JEV_ENABLED=1 e reinicie o backend."
        )
    if not settings.get("configured"):
        raise SystemExit("❌ O Jev não está configurado.")
    if settings.get("mode") != "shadow":
        raise SystemExit("❌ Esta etapa exige HAILA_JEV_MODE=shadow.")

    exp.OUT.mkdir(parents=True, exist_ok=True)
    baseline_path = exp.OUT / "baseline.jsonl"
    jev_path = exp.OUT / "jev.jsonl"

    baseline_rows = exp.read_jsonl(baseline_path)
    baseline = latest_successes(baseline_rows)
    done = latest_jev_ok(exp.read_jsonl(jev_path))

    eligible_ids = [
        c["case_id"]
        for c in exp.cases_100()
        if c["case_id"] in baseline
    ]
    pending = [cid for cid in eligible_ids if cid not in done]

    print("=" * 96)
    print("JEV SHADOW ROBUSTO — AVALIAÇÃO PARCIAL/INCREMENTAL")
    print("=" * 96)
    print(f"Baseline válidas disponíveis: {len(eligible_ids)}")
    print(f"Jev já concluído com status OK: {len(done)}")
    print(f"Pendentes para Jev agora: {len(pending)}")
    print("Este script NÃO gera novas questões e NÃO usa Groq.")
    print("Pode rodar novamente depois; ele só avalia as novas/pedentes.")

    for pos, cid in enumerate(pending, 1):
        b = baseline[cid]
        payload = {
            "question": b["question"],
            "specification": b.get("specification") or {},
            "reference": b.get("reference") or {},
        }

        print(f"\n[{pos}/{len(pending)}] {cid} | {b.get('area','-')}")
        success = False

        for attempt in range(1, args.max_retries + 1):
            started = time.perf_counter()
            try:
                response = exp.http_json(
                    "POST", "/evaluations/jev", payload, timeout=120
                )
                result = response.get("result") or {}
                prov = response.get("provenance") or {}
                criteria = result.get("criteria") or {}

                row = {
                    "case_id": cid,
                    "area": b.get("area"),
                    "request_id": b.get("request_id"),
                    "status": "OK",
                    "jev_wall_seconds": round(time.perf_counter() - started, 4),
                    "attempt": attempt,
                    "model_requested": prov.get("model_requested"),
                    "model_resolved": prov.get("model_resolved"),
                    "latency_ms": prov.get("latency_ms"),
                    "input_tokens": (prov.get("usage") or {}).get("input_tokens"),
                    "output_tokens": (prov.get("usage") or {}).get("output_tokens"),
                    "estimated_cost_usd": prov.get("estimated_cost_usd"),
                    "minimum_probability": result.get("minimum_probability"),
                    "mean_probability": result.get("mean_probability"),
                    "lowest_criterion": result.get("lowest_criterion"),
                    "requires_human_review": result.get("requires_human_review"),
                }
                for k in exp.CRITERIA:
                    row[k] = (criteria.get(k) or {}).get("probability_yes")

                exp.append_jsonl(jev_path, row)
                done[cid] = row
                success = True
                print(
                    f"✅ {cid} | min={row.get('minimum_probability')} | "
                    f"lowest={row.get('lowest_criterion')} | "
                    f"latency={row.get('latency_ms')} ms"
                )
                break

            except exp.HttpFailure as exc:
                row = {
                    "case_id": cid,
                    "area": b.get("area"),
                    "request_id": b.get("request_id"),
                    "status": f"HTTP_{exc.status}",
                    "jev_wall_seconds": round(time.perf_counter() - started, 4),
                    "attempt": attempt,
                    "error": str(exc),
                }
                exp.append_jsonl(jev_path, row)
                print(f"⚠️ Jev HTTP {exc.status} na tentativa {attempt}/{args.max_retries}")

                if exc.status in {429, 529} and attempt < args.max_retries:
                    wait = args.cooldown
                    try:
                        if exc.retry_after is not None:
                            wait = max(wait, float(exc.retry_after))
                    except Exception:
                        pass
                    print(f"Aguardando {wait:.0f}s...")
                    time.sleep(wait)
                else:
                    break

            except Exception as exc:
                row = {
                    "case_id": cid,
                    "area": b.get("area"),
                    "request_id": b.get("request_id"),
                    "status": "ERROR",
                    "jev_wall_seconds": round(time.perf_counter() - started, 4),
                    "attempt": attempt,
                    "error": f"{type(exc).__name__}: {exc}",
                }
                exp.append_jsonl(jev_path, row)
                print(f"❌ {type(exc).__name__}: {exc}")
                break

        if not success:
            print(f"⚠️ {cid} continua pendente e será tentada novamente no próximo uso.")

        if pos < len(pending) and args.delay > 0:
            time.sleep(args.delay)

    summary = export_summary(jev_path)
    print("\n" + "=" * 96)
    print("RESUMO JEV PARCIAL")
    print("=" * 96)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
