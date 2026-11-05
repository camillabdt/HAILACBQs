#!/usr/bin/env python3
"""Confere se o LoRA treinado está pronto para ser usado pelo HAILA."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from haila.slm_config import runtime_status  # noqa: E402

status = runtime_status()
print(json.dumps(status, ensure_ascii=False, indent=2))
if not status["configured"] or status["mode"] != "lora":
    raise SystemExit("SLM LoRA não está pronta.")
print("\n✅ Qwen + LoRA ENADE+POSCOMP pronto para gerar distratores no HAILA.")
