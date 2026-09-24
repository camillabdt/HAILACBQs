#!/usr/bin/env python3
"""Consolida o uso exato de tokens registrado nas respostas dos modelos."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


SUCCESS_STATES = {"COMPLETED", "GENERATION_COMPLETED"}


def add_usage(target: dict[str, int], usage: object) -> None:
    if not isinstance(usage, dict):
        return
    target["input"] += int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
    target["output"] += int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0)
    target["total"] += int(usage.get("total_tokens", 0) or 0)


def artifact_usages(artifacts: list[dict]) -> tuple[dict[str, int], dict[str, int]]:
    remote = {"input": 0, "output": 0, "total": 0}
    local = {"input": 0, "output": 0, "total": 0}
    for artifact in artifacts:
        provenance = artifact.get("provenance") or {}
        add_usage(remote, provenance.get("token_usage_remote"))
        add_usage(local, provenance.get("token_usage_local"))
    return remote, local


def normalize_condition(condition: str) -> str:
    return "C4_HAILA_COMPLETA" if condition == "C4" else condition


def load_rows(paths: list[Path]) -> list[dict]:
    rows = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        default_condition = normalize_condition(data.get("condition") or "C4_HAILA_COMPLETA")
        for item in data.get("items", []):
            condition = normalize_condition(item.get("condition") or default_condition)
            state = item.get("state") or (item.get("generation") or {}).get("state")
            artifacts = item.get("artifacts") or (item.get("history") or {}).get("artifacts") or []
            remote, local = artifact_usages(artifacts)
            rows.append(
                {
                    "source": str(path),
                    "condition": condition,
                    "spec_id": item.get("spec_id"),
                    "state": state,
                    "successful": state in SUCCESS_STATES,
                    "groq": remote,
                    "slm_local": local,
                }
            )
    return rows


def deduplicate(rows: list[dict]) -> list[dict]:
    """Mantém uma execução por condição/item, preferindo a concluída."""
    selected: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row["condition"], row["spec_id"])
        current = selected.get(key)
        if current is None or (row["successful"] and not current["successful"]):
            selected[key] = row
    return sorted(selected.values(), key=lambda row: (row["condition"], row["spec_id"]))


def summarize(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(
        lambda: {
            "items": 0,
            "successful_items": 0,
            "groq_input": 0,
            "groq_output": 0,
            "groq_total": 0,
            "slm_local_input": 0,
            "slm_local_output": 0,
            "slm_local_total": 0,
        }
    )
    for row in rows:
        group = grouped[row["condition"]]
        group["items"] += 1
        group["successful_items"] += int(row["successful"])
        group["groq_input"] += row["groq"]["input"]
        group["groq_output"] += row["groq"]["output"]
        group["groq_total"] += row["groq"]["total"]
        group["slm_local_input"] += row["slm_local"]["input"]
        group["slm_local_output"] += row["slm_local"]["output"]
        group["slm_local_total"] += row["slm_local"]["total"]

    summary = []
    for condition, group in sorted(grouped.items()):
        group["condition"] = condition
        group["mean_groq_total_per_item"] = round(group["groq_total"] / group["items"], 2)
        summary.append(group)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rows = deduplicate(load_rows(args.inputs))
    result = {
        "measurement": "exact provider usage persisted by HAILA",
        "cost_scope": "Groq tokens only; local SLM tokens reported separately",
        "deduplication": "one run per condition/spec_id, preferring a successful run",
        "rows": rows,
        "summary": summarize(rows),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
