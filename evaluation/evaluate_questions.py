#!/usr/bin/env python3
"""Triagem reprodutível das questões persistidas pela HAILA.

Os resultados automáticos descrevem propriedades observáveis. Eles não substituem
o parecer de especialistas sobre correção conceitual e valor pedagógico.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from haila.structural import avaliar_estrutura_enade


def norm(text: object) -> str:
    value = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(c for c in value if not unicodedata.combining(c))


def words(text: object) -> set[str]:
    stop = {"a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "um", "uma", "para", "por"}
    return {w for w in re.findall(r"[a-z0-9]+", norm(text)) if len(w) > 2 and w not in stop}


def flag(code: str, layer: str, field: str, evidence: str, severity: str = "review") -> dict:
    return {"codigo": code, "camada": layer, "campo": field, "evidencia": evidence, "severidade": severity}


def evaluate(spec: dict, q: dict) -> tuple[list[dict], dict]:
    flags = []
    for item in avaliar_estrutura_enade(q):
        flags.append(flag(item["codigo"], "deterministica", item.get("campo", "questao"), item.get("evidencia", ""), "block"))

    stem = str(q.get("enunciado") or "").strip()
    alternatives = [str(a or "").strip() for a in q.get("alternativas") or []]
    correct = q.get("correta")
    explanation = str(q.get("explicacao") or "").strip()

    if re.match(r"^(cite|descreva|explique|discorra)\b", norm(stem)):
        flags.append(flag("comando_resposta_aberta_em_item_objetivo", "linguistica", "enunciado", stem[:120]))
    foreign = sorted({token for token in ("estructura", "arquitectura", "requisito funcionales") if token in norm(" ".join(alternatives))})
    if foreign:
        flags.append(flag("idioma_inconsistente", "linguistica", "alternativas", ", ".join(foreign)))

    expected = " ".join(str(spec.get(k) or "") for k in ("objetivo_pedagogico", "objeto_conhecimento"))
    produced = " ".join(str(q.get(k) or "") for k in ("enunciado", "objeto_conhecimento", "competencia", "habilidade"))
    expected_words, produced_words = words(expected), words(produced)
    overlap = len(expected_words & produced_words) / max(1, len(expected_words))
    if expected_words and overlap < 0.20:
        flags.append(flag("possivel_desalinhamento_com_especificacao", "semantica_triagem", "objeto_conhecimento", f"sobreposição lexical={overlap:.2f}; requer confirmação humana"))
    requested_object = words(spec.get("objeto_conhecimento"))
    produced_object = words(q.get("objeto_conhecimento"))
    object_overlap = len(requested_object & produced_object) / max(1, len(requested_object))
    if requested_object and produced_object and object_overlap < 0.20:
        flags.append(flag(
            "possivel_desalinhamento_do_objeto_conhecimento",
            "semantica_triagem",
            "objeto_conhecimento",
            f"solicitado={spec.get('objeto_conhecimento')!r}; gerado={q.get('objeto_conhecimento')!r}; requer confirmação humana",
        ))

    if isinstance(correct, int) and 0 <= correct < len(alternatives):
        answer = alternatives[correct]
        if words(answer) and not (words(answer) & words(explanation)):
            flags.append(flag("explicacao_nao_nomeia_gabarito", "semantica_triagem", "explicacao", "a explicação não contém termos do gabarito"))

    lengths = [len(words(a)) for a in alternatives if a]
    if lengths and max(lengths) >= max(4, 3 * max(1, min(lengths))):
        flags.append(flag("alternativas_com_extensao_desequilibrada", "linguistica", "alternativas", f"palavras por alternativa={lengths}"))

    metrics = {
        "enunciado_caracteres": len(stem),
        "alternativas": len(alternatives),
        "sobreposicao_especificacao": round(overlap, 3),
        "sobreposicao_objeto_conhecimento": round(object_overlap, 3),
        "flags_bloqueio": sum(f["severidade"] == "block" for f in flags),
        "flags_revisao": sum(f["severidade"] == "review" for f in flags),
    }
    return flags, metrics


def load(db: Path) -> list[dict]:
    con = sqlite3.connect(db); con.row_factory = sqlite3.Row
    rows = list(con.execute("""
        SELECT r.id request_id, r.specification_json, r.state,
               v.version_number, v.question_json, v.provenance_json
        FROM requests r JOIN versions v ON v.request_id=r.id
        WHERE v.version_number=(SELECT MAX(v2.version_number) FROM versions v2 WHERE v2.request_id=r.id)
        ORDER BY r.created_at
    """))
    con.close()
    return [dict(r) for r in rows]


def render_md(report: dict) -> str:
    s = report["resumo"]
    lines = ["# Triagem automática das questões", "",
             "> Esta triagem identifica sinais observáveis. Correção conceitual, unicidade do gabarito, plausibilidade dos distratores e adequação pedagógica exigem revisão semântica humana ou experimental separada.", "",
             "## Resultado do piloto", "",
             f"- Questões avaliadas: {s['questoes']}",
             f"- Questões sem sinais automáticos: {s['sem_sinais']}",
             f"- Questões encaminhadas para revisão: {s['para_revisao']}",
             f"- Sinais de bloqueio estrutural: {s['flags_bloqueio']}",
             f"- Sinais de revisão: {s['flags_revisao']}", "", "## Por questão", ""]
    for item in report["itens"]:
        lines.append(f"### `{item['request_id']}`")
        lines.append("")
        lines.append(f"**Enunciado:** {item['questao'].get('enunciado','')}")
        lines.append("")
        if not item["flags"]:
            lines.append("Nenhum sinal automático encontrado.")
        else:
            for f in item["flags"]:
                lines.append(f"- **{f['codigo']}** [{f['camada']}]: {f['evidencia']}")
        lines.append("")
    lines += ["## Interpretação", "", "A ausência de sinais não equivale a aprovação pedagógica. Os itens sinalizados devem ser apresentados sem identificação da configuração a professores, usando a ficha de avaliação humana.", ""]
    return "\n".join(lines)


def human_sheet(path: Path, items: list[dict]) -> None:
    fields = ["item_id", "revisor", "formacao_area", "correcao_conceitual_1_5", "clareza_1_5", "alinhamento_1_5", "unicidade_gabarito_1_5", "qualidade_distratores_1_5", "estilo_enade_1_5", "decisao_APROVAR_CORRIGIR_REJEITAR", "comentarios"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
        for item in items: writer.writerow({"item_id": item["request_id"]})


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--db", type=Path, default=ROOT/"runtime/haila.sqlite3"); ap.add_argument("--out", type=Path, default=ROOT/"evaluation/results/question_quality_report.json"); args = ap.parse_args()
    items=[]
    for row in load(args.db):
        spec=json.loads(row["specification_json"]); q=json.loads(row["question_json"])
        flags, metrics=evaluate(spec,q)
        items.append({"request_id":row["request_id"],"state":row["state"],"version":row["version_number"],"especificacao":spec,"questao":q,"flags":flags,"metricas":metrics,"requer_revisao":bool(flags)})
    counts=Counter(f["severidade"] for i in items for f in i["flags"])
    report={"metodo":"triagem-deterministica-haila-v1","itens":items,"resumo":{"questoes":len(items),"sem_sinais":sum(not i["flags"] for i in items),"para_revisao":sum(i["requer_revisao"] for i in items),"flags_bloqueio":counts["block"],"flags_revisao":counts["review"]}}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    args.out.with_suffix(".md").write_text(render_md(report),encoding="utf-8")
    human_sheet(args.out.parent/"human_review_form.csv",items)
    print(json.dumps(report["resumo"],ensure_ascii=False,indent=2))
    return 0


if __name__ == "__main__": raise SystemExit(main())
