#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = "http://127.0.0.1:8000"
ROOT = Path.home() / "HAILA"
OUT_ROOT = ROOT / "output"
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
OUT_DIR = OUT_ROOT / f"teste-es-redes-metricas-{STAMP}"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TESTES = [
    {
        "nome": "engenharia_software",
        "payload": {
            "solicitante_id": "teste-metricas-es",
            "curso": "Computação",
            "exame": "ENADE",
            "componente": "ESPECIFICO",
            "objetivo_pedagogico": (
                "Avaliar se o estudante consegue identificar e classificar "
                "requisitos funcionais e não funcionais a partir de um cenário "
                "de desenvolvimento de software."
            ),
            "dificuldade": 3,
            "competencia": "Analisar especificações de requisitos de software.",
            "habilidade": "Classificar requisitos e relacioná-los às necessidades do sistema.",
            "objeto_conhecimento": "Engenharia de requisitos: requisitos funcionais e não funcionais.",
            "restricoes": [
                "Usar um cenário realista de sistema de software.",
                "Avaliar uma única decisão principal.",
                "Evitar pistas lexicais que revelem o gabarito.",
                "Manter apenas uma alternativa correta.",
                "Produzir quatro distratores plausíveis e do mesmo nível conceitual do gabarito."
            ],
            "max_tentativas": 3,
            "max_tentativas_distratores": 3
        }
    },
    {
        "nome": "redes",
        "payload": {
            "solicitante_id": "teste-metricas-redes",
            "curso": "Computação",
            "exame": "ENADE",
            "componente": "ESPECIFICO",
            "objetivo_pedagogico": (
                "Avaliar se o estudante consegue calcular e selecionar o prefixo "
                "IPv4 adequado para atender a uma necessidade de hosts ou "
                "para dividir uma rede em sub-redes."
            ),
            "dificuldade": 3,
            "competencia": "Analisar princípios de comunicação e organização de redes de computadores.",
            "habilidade": "Calcular o prefixo IPv4 adequado em uma situação de subnetting.",
            "objeto_conhecimento": "Endereçamento IPv4, CIDR e subnetting.",
            "restricoes": [
                "Avaliar somente subnetting; não combinar com roteamento, NAT, DHCP ou VLAN.",
                "O gabarito deve ser apenas um prefixo CIDR (/xx) ou uma máscara decimal IPv4 válida.",
                "Evitar cálculos excessivamente longos.",
                "Produzir alternativas plausíveis do mesmo tipo do gabarito.",
                "Manter apenas uma alternativa correta."
            ],
            "max_tentativas": 3,
            "max_tentativas_distratores": 3
        }
    },
]


def http_json(method: str, path: str, payload=None, timeout=1200):
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
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        raise RuntimeError(
            f"HTTP {exc.code} em {path}: "
            f"{json.dumps(parsed, ensure_ascii=False)}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Não consegui acessar {BASE}: {exc}") from exc


def token_totals(artifacts):
    groq = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }

    slm = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }

    for art in artifacts:
        prov = art.get("provenance") or {}

        remote = prov.get("token_usage_remote") or {}
        local = prov.get("token_usage_local") or {}

        for key in groq:
            groq[key] += int(remote.get(key) or 0)

        for key in slm:
            slm[key] += int(local.get(key) or 0)

    return groq, slm


def route_from_artifacts(artifacts):
    ds = [a for a in artifacts if a.get("kind") == "DISTRACTORS"]

    if not ds:
        return {
            "route": "",
            "model": "",
            "router": "",
            "strategy": "",
        }

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

    return {
        "route": route,
        "model": model,
        "router": prov.get("roteador", ""),
        "strategy": prov.get("estrategia", ""),
    }


def print_question(question):
    if not question:
        print("  SEM QUESTÃO FINAL")
        return

    print("\n  ENUNCIADO")
    print(" ", question.get("enunciado", "").strip())

    print("\n  ALTERNATIVAS")
    correta = question.get("correta")

    for i, alt in enumerate(question.get("alternativas", [])):
        mark = " ← GABARITO" if i == correta else ""
        print(f"   {chr(65+i)}) {alt}{mark}")

    print("\n  EXPLICAÇÃO")
    print(" ", question.get("explicacao", "").strip())


def main():
    print("=" * 84)
    print("HAILA — teste focado de Engenharia + Redes com métricas")
    print("=" * 84)

    _, health = http_json("GET", "/health", timeout=20)
    _, settings = http_json("GET", "/settings/groq", timeout=20)

    print("\nMODELO LLM:", settings.get("modelo"))
    print("SLM:", health.get("slm_base_model"))
    print("SLM mode:", health.get("slm_mode"))

    resultados = []

    for idx, teste in enumerate(TESTES, 1):
        nome = teste["nome"]
        payload = teste["payload"]

        print("\n" + "=" * 84)
        print(f"[{idx}/2] {nome}")
        print("=" * 84)

        started = time.perf_counter()

        try:
            _, created = http_json("POST", "/requests", payload, timeout=30)
            rid = created["id"]
            print("Request ID:", rid)

            _, generated = http_json(
                "POST",
                f"/requests/{rid}/generate",
                timeout=1800,
            )

            _, history = http_json(
                "GET",
                f"/requests/{rid}",
                timeout=30,
            )

            elapsed = time.perf_counter() - started

            req = history.get("request") or {}
            artifacts = history.get("artifacts") or []
            historical_flags = history.get("red_flags") or []

            latest = history.get("latest_version") or {}
            question = latest.get("question")

            state = generated.get("state") or req.get("state")
            final_flags = generated.get("red_flags") or []

            groq, slm = token_totals(artifacts)
            route = route_from_artifacts(artifacts)

            row = {
                "teste": nome,
                "request_id": rid,
                "state": state,
                "duration_seconds": round(elapsed, 2),

                "attempts": req.get("attempts"),
                "stem_attempts": req.get("stem_attempts"),
                "distractor_attempts": req.get("distractor_attempts"),

                "historical_red_flags": len(historical_flags),
                "final_red_flags": len(final_flags),

                "route": route["route"],
                "distractor_model": route["model"],
                "router": route["router"],
                "strategy": route["strategy"],

                "groq_prompt_tokens": groq["prompt_tokens"],
                "groq_completion_tokens": groq["completion_tokens"],
                "groq_total_tokens": groq["total_tokens"],

                "slm_input_tokens": slm["input_tokens"],
                "slm_output_tokens": slm["output_tokens"],
                "slm_total_tokens": slm["total_tokens"],

                "question_generated": bool(question),
            }

            resultados.append(row)

            print("Estado:", state)
            print(f"Tempo: {elapsed:.2f} s")
            print(
                "Tentativas:",
                req.get("attempts"),
                "| núcleo:",
                req.get("stem_attempts"),
                "| distratores:",
                req.get("distractor_attempts"),
            )

            print(
                "Flags históricas:",
                len(historical_flags),
                "| flags finais:",
                len(final_flags),
            )

            print(
                "Rota:",
                route["route"],
                "| modelo:",
                route["model"],
            )

            print(
                "Tokens Groq:",
                f"in={groq['prompt_tokens']}",
                f"out={groq['completion_tokens']}",
                f"total={groq['total_tokens']}",
            )

            print(
                "Tokens SLM local:",
                f"in={slm['input_tokens']}",
                f"out={slm['output_tokens']}",
                f"total={slm['total_tokens']}",
            )

            print_question(question)

            if historical_flags:
                print("\n  FLAGS HISTÓRICAS")
                for n, flag in enumerate(historical_flags, 1):
                    print(
                        f"   {n}.",
                        flag.get("codigo") or flag.get("code"),
                        "→",
                        flag.get("reparo") or flag.get("repair_target"),
                    )

            (OUT_DIR / f"{idx:02d}-{nome}.json").write_text(
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

        except Exception as exc:
            elapsed = time.perf_counter() - started
            error = str(exc)

            if "HTTP 429" in error:
                classe = "PROVIDER_LIMIT"
            elif "HTTP 500" in error:
                classe = "BACKEND_ERROR"
            else:
                classe = "ERROR"

            print(f"❌ {classe}: {error}")

            resultados.append({
                "teste": nome,
                "state": classe,
                "duration_seconds": round(elapsed, 2),
                "error": error,
            })

        if idx < len(TESTES):
            print("\nAguardando 10 s antes da próxima chamada...")
            time.sleep(10)

    resumo = {
        "timestamp": STAMP,
        "model": settings.get("modelo"),
        "slm_model": health.get("slm_base_model"),
        "slm_mode": health.get("slm_mode"),
        "results": resultados,
    }

    (OUT_DIR / "resumo.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n" + "=" * 84)
    print("RESUMO")
    print("=" * 84)

    for r in resultados:
        print(
            f"- {r['teste']}: {r.get('state')} | "
            f"{r.get('duration_seconds')} s | "
            f"route={r.get('route', '-')} | "
            f"Groq={r.get('groq_total_tokens', '-')} tok | "
            f"SLM={r.get('slm_total_tokens', '-')} tok | "
            f"flags_hist={r.get('historical_red_flags', '-')}"
        )

    print("\nResultados completos:")
    print(OUT_DIR)


if __name__ == "__main__":
    main()
