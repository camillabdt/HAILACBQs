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
OUT_ROOT = Path.home() / "HAILA" / "output"
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
OUT_DIR = OUT_ROOT / f"teste-geracao-lora-{STAMP}"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TESTES = [
    {
        "nome": "banco_dados",
        "payload": {
            "solicitante_id": "teste-lora-bd",
            "curso": "Computação",
            "exame": "ENADE",
            "componente": "ESPECIFICO",
            "objetivo_pedagogico": (
                "Avaliar se o estudante consegue distinguir leitura suja, "
                "leitura não repetível e leitura fantasma em cenários de "
                "concorrência de transações em bancos de dados relacionais."
            ),
            "dificuldade": 3,
            "competencia": "Analisar mecanismos de controle de concorrência em sistemas de banco de dados.",
            "habilidade": "Distinguir anomalias de concorrência a partir de uma situação-problema.",
            "objeto_conhecimento": "Transações, isolamento e controle de concorrência em bancos de dados.",
            "restricoes": [
                "Gerar uma questão contextualizada.",
                "Evitar alternativas obviamente absurdas.",
                "Manter apenas uma alternativa correta."
            ],
            "max_tentativas": 3,
            "max_tentativas_distratores": 3
        }
    },
    {
        "nome": "engenharia_software",
        "payload": {
            "solicitante_id": "teste-lora-es",
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
                "Evitar pistas lexicais que revelem o gabarito.",
                "Manter apenas uma alternativa correta."
            ],
            "max_tentativas": 3,
            "max_tentativas_distratores": 3
        }
    },
    {
        "nome": "redes",
        "payload": {
            "solicitante_id": "teste-lora-redes",
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


def http_json(method: str, path: str, payload=None, timeout=900):
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
        raise RuntimeError(f"HTTP {exc.code} em {path}: {json.dumps(parsed, ensure_ascii=False)}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Não consegui acessar {BASE}: {exc}") from exc


def letra(idx):
    try:
        return chr(ord("A") + int(idx))
    except Exception:
        return "?"


def imprimir_questao(question):
    if not question:
        print("  (nenhuma versão de questão montada)")
        return
    print("\n  ENUNCIADO")
    print(" ", question.get("enunciado", "").strip())
    print("\n  ALTERNATIVAS")
    correta = question.get("correta")
    for i, alt in enumerate(question.get("alternativas", [])):
        marca = "  ← GABARITO" if i == correta else ""
        print(f"   {letra(i)}) {alt}{marca}")
    if question.get("explicacao"):
        print("\n  EXPLICAÇÃO")
        print(" ", question["explicacao"])


print("=" * 72)
print("HAILA — diagnóstico + 3 gerações com Qwen/LoRA")
print("=" * 72)

try:
    _, health = http_json("GET", "/health", timeout=20)
except Exception as exc:
    print(f"\n❌ {exc}")
    print("Inicie o backend antes de rodar este teste.")
    sys.exit(1)

print("\n[1] HEALTH")
print(json.dumps(health, ensure_ascii=False, indent=2))

problemas = []
if health.get("slm_mode") != "lora":
    problemas.append(f"slm_mode={health.get('slm_mode')!r}, esperado 'lora'")
if health.get("slm_adapter_loaded") is not True:
    problemas.append("slm_adapter_loaded não é true")
if health.get("slm_configured") is not True:
    problemas.append("slm_configured não é true")
if health.get("llm_configured") is not True:
    problemas.append("llm_configured não é true (Groq precisa ser configurada nesta sessão)")

if problemas:
    print("\n⚠️ NÃO VOU GERAR AINDA:")
    for p in problemas:
        print(" -", p)
    if health.get("llm_configured") is not True:
        print("\nAbra o Studio → Configuração Groq, informe sua chave e depois rode este teste novamente.")
    sys.exit(2)

print("\n✅ Runtime pronto: LLM + Qwen/LoRA disponíveis.")

resumo = []

for numero, teste in enumerate(TESTES, 1):
    nome = teste["nome"]
    payload = teste["payload"]
    print("\n" + "=" * 72)
    print(f"[{numero}/3] GERANDO: {nome}")
    print("=" * 72)

    inicio = time.perf_counter()
    try:
        _, criado = http_json("POST", "/requests", payload, timeout=30)
        rid = criado["id"]
        print("Request ID:", rid)

        _, gerado = http_json("POST", f"/requests/{rid}/generate", timeout=1200)
        _, historico = http_json("GET", f"/requests/{rid}", timeout=30)

        duracao = time.perf_counter() - inicio
        state = gerado.get("state") or historico.get("request", {}).get("state")
        latest = historico.get("latest_version")
        question = (latest or {}).get("question") if latest else None

        flags = historico.get("red_flags", [])
        events = historico.get("events", [])
        artifacts = historico.get("artifacts", [])

        arquivo = OUT_DIR / f"{numero:02d}-{nome}.json"
        arquivo.write_text(
            json.dumps(
                {
                    "input": payload,
                    "generate_response": gerado,
                    "history": historico,
                    "duration_seconds": round(duracao, 2),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(f"Estado final: {state}")
        print(f"Tempo: {duracao:.1f} s")
        print(f"Red flags registradas: {len(flags)}")
        print(f"Eventos: {len(events)} | Artefatos: {len(artifacts)}")
        imprimir_questao(question)

        slm_artifacts = [a for a in artifacts if a.get("kind") == "DISTRACTORS"]
        if slm_artifacts:
            prov = slm_artifacts[-1].get("provenance", {})
            print("\n  PROVENIÊNCIA DO ÚLTIMO PASSO DE DISTRATORES")
            print(" ", json.dumps(prov, ensure_ascii=False))

        resumo.append({
            "teste": nome,
            "request_id": rid,
            "state": state,
            "duration_seconds": round(duracao, 2),
            "red_flags": len(flags),
            "question_generated": bool(question),
            "arquivo": str(arquivo),
        })

    except Exception as exc:
        duracao = time.perf_counter() - inicio
        print(f"\n❌ Falhou após {duracao:.1f}s: {exc}")
        resumo.append({
            "teste": nome,
            "state": "ERROR",
            "duration_seconds": round(duracao, 2),
            "error": str(exc),
        })

(OUT_DIR / "resumo.json").write_text(
    json.dumps(resumo, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print("\n" + "=" * 72)
print("RESUMO")
print("=" * 72)
for r in resumo:
    print(
        f"- {r['teste']}: {r.get('state')} | "
        f"{r.get('duration_seconds')} s | "
        f"red flags={r.get('red_flags', '-')}"
    )

print(f"\nResultados completos salvos em:\n{OUT_DIR}")
print("\n✅ Teste encerrado.")
