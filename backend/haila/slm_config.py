"""Configuração centralizada da SLM local usada pelo HAILA.

A versão de produção usa Qwen2.5-1.5B-Instruct com o LoRA ENADE+POSCOMP
selecionado no experimento de 2026-10-02. Caminhos relativos são sempre
resolvidos a partir da raiz do projeto, independentemente do cwd do backend.
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QWEN_BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
DEFAULT_QWEN_ADAPTER_RELATIVE = Path("adapters/qwen-distratores-enade-poscomp")


def slm_backend() -> str:
    return os.getenv("HAILA_SLM_BACKEND", "qwen").strip().casefold()


def slm_base_model(backend: str | None = None) -> str:
    backend = backend or slm_backend()
    default = (
        DEFAULT_QWEN_BASE_MODEL
        if backend == "qwen"
        else "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    )
    return os.getenv("HAILA_SLM_BASE_MODEL", default).strip() or default


def resolve_adapter_path(raw: str | Path | None = None, backend: str | None = None) -> Path | None:
    """Resolve o adapter a partir da raiz do projeto.

    Para Qwen, quando HAILA_SLM_ADAPTER_PATH estiver vazio, usa automaticamente
    o LoRA ENADE+POSCOMP incluído no projeto.
    """
    backend = backend or slm_backend()
    if raw is None:
        raw = os.getenv("HAILA_SLM_ADAPTER_PATH", "")
    texto = str(raw).strip()
    if not texto:
        if backend == "qwen":
            return (PROJECT_ROOT / DEFAULT_QWEN_ADAPTER_RELATIVE).resolve()
        return None
    path = Path(texto).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def adapter_is_complete(path: Path | None) -> bool:
    if path is None or not path.is_dir():
        return False
    return (path / "adapter_config.json").is_file() and (path / "adapter_model.safetensors").is_file()


def allow_base_qwen() -> bool:
    """Qwen base só é permitido quando explicitamente habilitado para ablação."""
    return os.getenv("HAILA_ALLOW_BASE_QWEN", "0").strip() == "1"


def runtime_status() -> dict[str, object]:
    backend = slm_backend()
    path = resolve_adapter_path(backend=backend)
    adapter_ok = adapter_is_complete(path)

    if backend == "qwen":
        if adapter_ok:
            mode = "lora"
            configured = True
        elif allow_base_qwen():
            mode = "base"
            configured = True
        else:
            mode = "adapter_missing"
            configured = False
    elif backend == "tinyllama":
        mode = "lora" if adapter_ok else "adapter_missing"
        configured = adapter_ok
    else:
        mode = "invalid_backend"
        configured = False

    return {
        "backend": backend,
        "base_model": slm_base_model(backend),
        "adapter_path": str(path) if path else None,
        "adapter_loaded": adapter_ok,
        "mode": mode,
        "configured": configured,
        "allow_base_qwen": allow_base_qwen(),
    }
