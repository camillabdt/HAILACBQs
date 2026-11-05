#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from collections import Counter

import experimento_100_haila_jev_pareado as exp


def successful_by_case(rows):
    out = {}
    for row in rows:
        if row.get("state") == "GENERATION_COMPLETED" and row.get("question"):
            out[row["case_id"]] = row
    return out


def append_row(path, row):
    exp.append_jsonl(path, row)


def export_clean(progress):
    rows = exp.read_jsonl(progress)
    successes = successful_by_case(rows)
    ordered = [
        successes[c["case_id"]]
        for c in exp.cases_100()
        if c["case_id"] in successes
    ]

    if ordered:
        exclude = {"specification", "question", "reference"}
        flat = [{k: v for k, v in r.items() if k not in exclude} for r in ordered]
        fields = []
        for row in flat:
            for key in row:
                if key not in fields:
                    fields.append(key)
        with (exp.OUT / "baseline_metricas_limpo.csv").open(
            "w", encoding="utf-8", newline=""
        ) as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerows(flat)

    summary = {
        "n_successful_unique_questions": len(ordered),
        "target": 100,
        "completion_rate_vs_target": len(ordered) / 100,
        "mean_wall_seconds": (
            statistics.mean([float(r["wall_seconds"]) for r in ordered])
            if ordered else None
        ),
        "median_wall_seconds": (
            statistics.median([float(r["wall_seconds"]) for r in ordered])
            if ordered else None
        ),
        "groq_tokens_total": sum(int(r.get("groq_total_tokens") or 0) for r in ordered),
        "slm_tokens_total": sum(int(r.get("slm_total_tokens") or 0) for r in ordered),
        "route_counts": dict(Counter(r.get("route") for r in ordered if r.get("route"))),
        "note": (
            "Somente um GENERATION_COMPLETED por case_id entra neste resumo. "
            "Registros HTTP_429/ERROR permanecem no baseline.jsonl apenas para auditoria."
        ),
    }
    (exp.OUT / "baseline_resumo_limpo.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=45.0)
    ap.add_argument("--cooldown-429", type=float, default=180.0)
    ap.add_argument("--max-case-retries", type=int, default=3)
    ap.add_argument("--stop-after-consecutive-429", type=int, default=3)
    ap.add_argument("--error-delay", type=float, default=10.0)
    args = ap.parse_args()

    settings = exp.http_json("GET", "/settings/jev", timeout=20)
    if settings.get("enabled"):
        raise SystemExit(
            "❌ O Jev deve continuar desligado durante a baseline. "
            "Defina HAILA_JEV_ENABLED=0 e reinicie o backend."
        )

    exp.OUT.mkdir(parents=True, exist_ok=True)
    progress = exp.OUT / "baseline.jsonl"
    rows = exp.read_jsonl(progress)
    successes = successful_by_case(rows)

    print("=" * 96)
    print("CONTINUAÇÃO ROBUSTA — BASELINE 100 SEM JEV")
    print("=" * 96)
    print(f"Sucessos preservados: {len(successes)}/100")
    print("Erros antigos NÃO contam como concluídos.")
    print("Após 429, o script cria uma NOVA solicitação; não reutiliza a que ficou terminal.")
    print("Ctrl+C é seguro. Rode novamente para continuar.")

    consecutive_429 = 0

    for idx, case in enumerate(exp.cases_100(), start=1):
        cid = case["case_id"]
        if cid in successes:
            continue

        payload = exp.payload_for(case)
        completed = False

        for outer_try in range(1, args.max_case_retries + 1):
            print(
                f"\n[{idx}/100] {cid} | {case['area']} | "
                f"tentativa externa {outer_try}/{args.max_case_retries}"
            )
            started = time.perf_counter()
            rid = None

            try:
                created = exp.http_json("POST", "/requests", payload, timeout=30)
                rid = created["id"]
                generated = exp.http_json(
                    "POST", f"/requests/{rid}/generate", timeout=1800
                )
                history = exp.http_json("GET", f"/requests/{rid}", timeout=30)

                req = history.get("request") or {}
                latest = history.get("latest_version") or {}
                question = latest.get("question")
                ref_art = exp.last_artifact(history, "REFERENCE")

                row = {
                    "case_id": cid,
                    "area": case["area"],
                    "subtema": case["subtema"],
                    "repetition": case["repetition"],
                    "request_id": rid,
                    "specification": payload,
                    "state": generated.get("state"),
                    "wall_seconds": round(time.perf_counter() - started, 4),
                    "outer_case_try": outer_try,
                    "attempts": req.get("attempts"),
                    "stem_attempts": req.get("stem_attempts"),
                    "distractor_attempts": req.get("distractor_attempts"),
                    "historical_red_flags": len(history.get("red_flags") or []),
                    "final_red_flags": len(generated.get("red_flags") or []),
                    "question": question,
                    "reference": (ref_art or {}).get("payload") or {},
                    **exp.route_info(history),
                    **exp.token_usage(history),
                }
                append_row(progress, row)

                if row["state"] == "GENERATION_COMPLETED" and question:
                    successes[cid] = row
                    completed = True
                    consecutive_429 = 0
                    print(
                        f"✅ {cid} concluída | {row['wall_seconds']}s | "
                        f"route={row.get('route') or '-'} | flags={row.get('final_red_flags')}"
                    )
                    break

                print(
                    f"⚠️ {cid} terminou em {row['state']}. "
                    "Se houver nova tentativa, será criada outra solicitação."
                )
                time.sleep(args.error_delay)

            except exp.HttpFailure as exc:
                row = {
                    "case_id": cid,
                    "area": case["area"],
                    "subtema": case["subtema"],
                    "repetition": case["repetition"],
                    "request_id": rid,
                    "specification": payload,
                    "state": f"HTTP_{exc.status}",
                    "wall_seconds": round(time.perf_counter() - started, 4),
                    "outer_case_try": outer_try,
                    "error": str(exc),
                    "question": None,
                    "reference": {},
                }
                append_row(progress, row)

                if exc.status == 429:
                    consecutive_429 += 1
                    print(
                        f"⚠️ 429 real da Groq. Essa solicitação ficou terminal. "
                        f"Não será reutilizada. Sequência de 429: {consecutive_429}."
                    )

                    if consecutive_429 >= args.stop_after_consecutive_429:
                        print(
                            "\n⛔ Três 429 consecutivos. Parando com segurança para "
                            "não desperdiçar chamadas. Tente novamente quando a cota renovar."
                        )
                        summary = export_clean(progress)
                        print(json.dumps(summary, ensure_ascii=False, indent=2))
                        return

                    print(f"Aguardando {args.cooldown_429:.0f}s antes de uma NOVA solicitação...")
                    time.sleep(args.cooldown_429)
                else:
                    print("❌", exc)
                    time.sleep(args.error_delay)

            except Exception as exc:
                row = {
                    "case_id": cid,
                    "area": case["area"],
                    "subtema": case["subtema"],
                    "repetition": case["repetition"],
                    "request_id": rid,
                    "specification": payload,
                    "state": "ERROR",
                    "wall_seconds": round(time.perf_counter() - started, 4),
                    "outer_case_try": outer_try,
                    "error": f"{type(exc).__name__}: {exc}",
                    "question": None,
                    "reference": {},
                }
                append_row(progress, row)
                print("❌", type(exc).__name__, exc)
                time.sleep(args.error_delay)

        if not completed:
            print(
                f"⚠️ {cid} ainda não foi concluída. Ela continuará pendente "
                "na próxima execução."
            )

        if len(successes) < 100 and args.delay > 0:
            time.sleep(args.delay)

    summary = export_clean(progress)
    print("\n" + "=" * 96)
    print("BASELINE FINAL")
    print("=" * 96)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
