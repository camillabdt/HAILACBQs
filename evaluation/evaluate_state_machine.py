#!/usr/bin/env python3
"""Avalia conformidade arquitetural da HAILA a partir da máquina de estados."""
from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
import sys
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from haila.domain import Estado, TRANSICOES_PERMITIDAS
from haila.repository import HailaRepository

TERMINAIS = {Estado.GENERATION_COMPLETED, Estado.ATTEMPTS_EXHAUSTED, Estado.GENERATION_FAILED}
ARTEFATOS_CONCLUIDOS = {"REFERENCE", "STEM", "DISTRACTORS", "DETERMINISTIC_RED_FLAGS"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def graph_checks() -> list[dict]:
    checks = []
    definidos = set(Estado)
    origens = set(TRANSICOES_PERMITIDAS)
    destinos = {d for ds in TRANSICOES_PERMITIDAS.values() for d in ds}
    checks.append(check("todos_estados_possuem_regra", definidos == origens,
                        f"definidos={len(definidos)}, origens={len(origens)}"))
    checks.append(check("destinos_sao_estados_validos", destinos <= definidos,
                        f"destinos_desconhecidos={sorted((destinos-definidos), key=str)}"))
    checks.append(check("terminais_sem_saida", all(not TRANSICOES_PERMITIDAS[s] for s in TERMINAIS),
                        ", ".join(s.value for s in TERMINAIS)))
    visitados = {Estado.REQUESTED}; fila = deque([Estado.REQUESTED])
    while fila:
        atual = fila.popleft()
        for prox in TRANSICOES_PERMITIDAS[atual]:
            if prox not in visitados:
                visitados.add(prox); fila.append(prox)
    checks.append(check("todos_estados_alcancaveis", visitados == definidos,
                        f"inalcancáveis={sorted(s.value for s in definidos-visitados)}"))
    return checks


def check(nome: str, passou: bool, evidencia: str) -> dict:
    return {"check": nome, "passou": bool(passou), "evidencia": evidencia}


def repository_guard_check() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        repo = HailaRepository(Path(tmp) / "guard.sqlite3")
        rid = repo.create_request("avaliacao-arquitetura", {"objetivo": "teste"}, 1, 1)
        try:
            repo.transition(rid, None, Estado.GENERATION_COMPLETED, "EVALUATION", "transição inválida proposital")
        except RuntimeError as exc:
            return check("repositorio_rejeita_transicao_invalida", True, str(exc))
        return check("repositorio_rejeita_transicao_invalida", False, "REQUESTED->GENERATION_COMPLETED foi aceita")


def audit_database(path: Path, request_ids: set[str] | None = None) -> tuple[list[dict], dict]:
    if not path.exists():
        return [check("banco_existe", False, str(path))], {"requests": 0}
    con = sqlite3.connect(path); con.row_factory = sqlite3.Row
    requests = list(con.execute("SELECT * FROM requests ORDER BY created_at"))
    if request_ids is not None:
        requests = [request for request in requests if request["id"] in request_ids]
    results=[]; state_counts=Counter(); transition_counts=Counter(); completed=0
    for request in requests:
        rid=request["id"]; state_counts[request["state"]]+=1
        events=list(con.execute("SELECT * FROM events WHERE request_id=? ORDER BY id",(rid,)))
        artifacts=list(con.execute("SELECT kind,payload_json,provenance_json FROM artifacts WHERE request_id=?",(rid,)))
        versions=list(con.execute("SELECT question_json FROM versions WHERE request_id=? ORDER BY version_number",(rid,)))
        issues=[]
        if not events or events[0]["to_state"] != Estado.REQUESTED.value:
            issues.append("histórico não inicia em REQUESTED")
        for event in events[1:]:
            old=Estado(event["from_state"]); new=Estado(event["to_state"])
            transition_counts[f"{old.value}->{new.value}"] += 1
            if old != new and new not in TRANSICOES_PERMITIDAS[old]:
                issues.append(f"transição inválida {old.value}->{new.value}")
        if events and events[-1]["to_state"] != request["state"]:
            issues.append("último evento diverge do estado persistido")
        for artifact in artifacts:
            try:
                json.loads(artifact["payload_json"]); json.loads(artifact["provenance_json"])
            except json.JSONDecodeError:
                issues.append(f"JSON inválido no artefato {artifact['kind']}")
        if request["state"] == Estado.GENERATION_COMPLETED.value:
            completed += 1
            kinds={a["kind"] for a in artifacts}
            missing=ARTEFATOS_CONCLUIDOS-kinds
            if missing: issues.append(f"artefatos ausentes: {sorted(missing)}")
            if not versions:
                issues.append("conclusão sem versão")
            else:
                q=json.loads(versions[-1]["question_json"]); alts=q.get("alternativas") or []; correct=q.get("correta")
                if len(alts)!=5: issues.append(f"alternativas={len(alts)}, esperado=5")
                if not isinstance(correct,int) or not 0 <= correct < len(alts): issues.append("índice de gabarito inválido")
        results.append({"request_id":rid,"estado":request["state"],"eventos":len(events),
                        "artefatos":len(artifacts),"versoes":len(versions),"conforme":not issues,"problemas":issues})
    con.close()
    summary={"requests":len(requests),"completed":completed,"conforming":sum(r["conforme"] for r in results),
             "state_counts":dict(state_counts),"transition_counts":dict(transition_counts)}
    return results,summary


def markdown(report: dict) -> str:
    lines=["# Avaliação da máquina de estados da HAILA","",f"Executada em: {report['executed_at']}","",
           "## Fundamentação", "", "A máquina de estados é avaliada como modelo comportamental da arquitetura. "
           "Os testes verificam completude do grafo, alcançabilidade, terminação, rejeição de transições inválidas e conformidade dos históricos persistidos.","",
           "## Verificações do modelo",""]
    for c in report["model_checks"]:
        lines.append(f"- {'PASSOU' if c['passou'] else 'FALHOU'} - **{c['check']}**: {c['evidencia']}")
    s=report["database_summary"]
    lines += ["","## Histórico real","",f"- Solicitações auditadas: {s['requests']}",f"- Gerações concluídas: {s['completed']}",
              f"- Históricos conformes: {s['conforming']} de {s['requests']}","", "### Estados observados",""]
    for state,count in sorted(s.get("state_counts",{}).items()): lines.append(f"- {state}: {count}")
    lines += ["","### Solicitações com problemas",""]
    bad=[r for r in report["requests"] if not r["conforme"]]
    if not bad: lines.append("Nenhuma inconformidade encontrada nos históricos disponíveis.")
    for r in bad: lines.append(f"- `{r['request_id']}` ({r['estado']}): {'; '.join(r['problemas'])}")
    lines += ["","## Limite da conclusão","", "Conformidade com a máquina de estados demonstra controle do fluxo e rastreabilidade. "
              "Ela não demonstra correção conceitual, qualidade pedagógica ou validade psicométrica das questões.",""]
    return "\n".join(lines)


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--db",type=Path,default=Path("runtime/haila.sqlite3")); ap.add_argument("--out",type=Path,default=Path("evaluation/results/state_machine_report.json")); ap.add_argument("--run-file",type=Path,help="arquivo JSON da execução C4 usado para restringir os IDs auditados"); args=ap.parse_args()
    request_ids=None
    if args.run_file:
        run=json.loads(args.run_file.read_text(encoding="utf-8")); request_ids=set()
        for item in run.get("items",[]):
            rid=item.get("request_id") or (item.get("generation") or {}).get("request_id") or (item.get("created") or {}).get("request_id") or (item.get("created") or {}).get("id")
            if rid: request_ids.add(rid)
        if not request_ids: raise SystemExit(f"nenhum request_id encontrado em {args.run_file}")
    model=graph_checks()+[repository_guard_check()]
    requests,summary=audit_database(args.db,request_ids)
    report={"executed_at":now(),"database":str(args.db),"model_checks":model,"database_summary":summary,"requests":requests,
            "scope":{"run_file":str(args.run_file) if args.run_file else None,"request_ids":sorted(request_ids) if request_ids is not None else None},
            "all_model_checks_passed":all(c["passou"] for c in model),"all_histories_conforming":all(r["conforme"] for r in requests)}
    args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    args.out.with_suffix(".md").write_text(markdown(report),encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("all_model_checks_passed","all_histories_conforming","database_summary")},ensure_ascii=False,indent=2))
    return 0 if report["all_model_checks_passed"] and report["all_histories_conforming"] else 1

if __name__ == "__main__": raise SystemExit(main())
