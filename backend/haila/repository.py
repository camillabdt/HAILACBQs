from __future__ import annotations
import json, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .domain import Estado, TRANSICOES_PERMITIDAS

def agora(): return datetime.now(timezone.utc).isoformat()


def _normalizar_flag_visual(flag):
    if not isinstance(flag, dict):
        return {"code": "alerta", "stage": "QUALIDADE", "field": "", "evidence": str(flag), "repair_target": ""}
    return {
        "code": flag.get("codigo") or flag.get("code") or "alerta",
        "stage": flag.get("etapa") or flag.get("stage") or "QUALIDADE",
        "field": flag.get("campo") or flag.get("field") or "",
        "evidence": flag.get("evidencia") or flag.get("evidence") or "",
        "repair_target": flag.get("reparo") or flag.get("repair_target") or "",
    }


def _quality_trace(req, artifacts, flags, events):
    """Build a compact, read-only quality/audit summary for the Studio.

    The database remains append-only.  This function only derives a view from
    already persisted artifacts, red flags and events so the UI can distinguish
    final warnings from problems that were detected and repaired during generation.
    """
    latest_summary = next(
        (a for a in reversed(artifacts) if a.get("kind") == "QUALITY_SUMMARY"),
        None,
    )
    summary_payload = (latest_summary or {}).get("payload") or {}
    final_warnings = [
        _normalizar_flag_visual(item)
        for item in (summary_payload.get("warnings") or [])
    ]

    treated = []
    for artifact in artifacts:
        kind = artifact.get("kind")
        payload = artifact.get("payload") or {}
        prov = artifact.get("provenance") or {}
        texto = payload.get("texto") if isinstance(payload, dict) else None

        if kind == "DISTRACTOR_CANDIDATE_REJECTED":
            artifact_flags = prov.get("flags") or []
            if artifact_flags:
                for raw in artifact_flags:
                    flag = _normalizar_flag_visual(raw)
                    treated.append({
                        **flag,
                        "type": "red_flag_tratada",
                        "candidate": texto or raw.get("alternativa_rejeitada") or "",
                        "action": "distrator_rejeitado",
                    })
            else:
                treated.append({
                    "type": "red_flag_tratada",
                    "code": "distrator_rejeitado",
                    "stage": "DISTRATORES",
                    "field": "alternativas",
                    "evidence": prov.get("reason") or "candidato rejeitado pelo filtro estrutural",
                    "repair_target": "DISTRATORES",
                    "candidate": texto or "",
                    "action": "distrator_rejeitado",
                })

        elif kind == "DISTRACTOR_CANDIDATE_REJECTED_QUALITY":
            treated.append({
                "type": "rejeicao_qualidade",
                "code": prov.get("quality_code") or "qualidade_distrator",
                "stage": "DISTRATORES",
                "field": "alternativas",
                "evidence": prov.get("reason") or "candidato rejeitado pela guarda de qualidade",
                "repair_target": "DISTRATORES",
                "candidate": texto or "",
                "action": "distrator_rejeitado",
            })

    promotions = []
    for artifact in artifacts:
        if artifact.get("kind") != "DISTRACTOR_RESERVE_PROMOTED":
            continue
        payload = artifact.get("payload") or {}
        prov = artifact.get("provenance") or {}
        promotions.append({
            "candidate": payload.get("texto") if isinstance(payload, dict) else "",
            "reason": prov.get("reason") or "reserva promovida após rejeição localizada",
            "check": prov.get("check"),
        })

    batches = [a for a in artifacts if a.get("kind") == "DISTRACTOR_BATCH"]
    generated = sum(
        len(a.get("payload") or [])
        for a in batches
        if isinstance(a.get("payload"), list)
    )
    accepted = sum(a.get("kind") == "DISTRACTOR_CANDIDATE_ACCEPTED" for a in artifacts)
    reserve_saved = sum(a.get("kind") == "DISTRACTOR_CANDIDATE_RESERVE" for a in artifacts)
    structural_rejections = sum(a.get("kind") == "DISTRACTOR_CANDIDATE_REJECTED" for a in artifacts)
    quality_rejections = sum(a.get("kind") == "DISTRACTOR_CANDIDATE_REJECTED_QUALITY" for a in artifacts)
    gate_checks = sum(a.get("kind") == "DISTRACTOR_QUALITY_GATE" for a in artifacts)

    duration_seconds = None
    timestamps = []
    for event in events:
        raw = event.get("created_at")
        if not raw:
            continue
        try:
            timestamps.append(datetime.fromisoformat(raw.replace("Z", "+00:00")))
        except (TypeError, ValueError):
            pass
    if len(timestamps) >= 2:
        duration_seconds = round((max(timestamps) - min(timestamps)).total_seconds(), 2)

    return {
        "final_warnings": final_warnings,
        "final_warning_count": len(final_warnings),
        "historical_red_flags": [
            {
                "code": f.get("code") or "alerta",
                "stage": f.get("stage") or "",
                "field": f.get("field") or "",
                "evidence": f.get("evidence") or "",
                "repair_target": f.get("repair_target") or "",
            }
            for f in flags
        ],
        "historical_red_flag_count": len(flags),
        "treated_occurrences": treated,
        "treated_occurrence_count": len(treated),
        "reserve_promotions": promotions,
        "reserve_promotion_count": len(promotions),
        "metrics": {
            "stem_attempts": req.get("stem_attempts", 0),
            "slm_calls": req.get("distractor_attempts", 0),
            "distractor_batches": len(batches),
            "candidates_generated": generated,
            "candidates_accepted_active": accepted,
            "candidates_saved_as_reserve": reserve_saved,
            "structural_rejections": structural_rejections,
            "quality_rejections": quality_rejections,
            "quality_gate_checks": gate_checks,
            "active_distractors": summary_payload.get("active_distractors"),
            "reserve_distractors": summary_payload.get("reserve_distractors"),
            "candidate_bank_size": summary_payload.get("candidate_bank_size"),
            "duration_seconds": duration_seconds,
        },
    }

class HailaRepository:
    """Registro append-only de eventos, artefatos, versões e pareceres da HAILA."""
    def __init__(self, caminho: str | Path = "runtime/haila.sqlite3"):
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho = str(caminho); self._init_schema()
    def _connect(self):
        con = sqlite3.connect(self.caminho); con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON"); return con
    def _init_schema(self):
        with self._connect() as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY, solicitante_id TEXT NOT NULL,state TEXT NOT NULL,
              specification_json TEXT NOT NULL,max_attempts INTEGER NOT NULL,max_distractor_attempts INTEGER NOT NULL,
              attempts INTEGER NOT NULL DEFAULT 0,stem_attempts INTEGER NOT NULL DEFAULT 0,distractor_attempts INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS versions(id TEXT PRIMARY KEY,request_id TEXT NOT NULL REFERENCES requests(id),
              version_number INTEGER NOT NULL,question_json TEXT NOT NULL,provenance_json TEXT NOT NULL,created_at TEXT NOT NULL,
              UNIQUE(request_id,version_number));
            CREATE TABLE IF NOT EXISTS artifacts(id INTEGER PRIMARY KEY AUTOINCREMENT,request_id TEXT NOT NULL REFERENCES requests(id),
              kind TEXT NOT NULL,payload_json TEXT NOT NULL,provenance_json TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS red_flags(id INTEGER PRIMARY KEY AUTOINCREMENT,request_id TEXT NOT NULL REFERENCES requests(id),
              code TEXT NOT NULL,stage TEXT NOT NULL,field TEXT NOT NULL,evidence TEXT NOT NULL,repair_target TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,request_id TEXT NOT NULL REFERENCES requests(id),
              version_id TEXT,from_state TEXT,to_state TEXT NOT NULL,component TEXT NOT NULL,reason TEXT,evidence_json TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY,request_id TEXT NOT NULL REFERENCES requests(id),
              version_id TEXT NOT NULL REFERENCES versions(id),reviewer_role TEXT NOT NULL,reviewer_name TEXT NOT NULL,
              reviewer_kind TEXT NOT NULL,decision TEXT NOT NULL,audit_percentage INTEGER NOT NULL,comments TEXT NOT NULL,
              red_flags_json TEXT NOT NULL,model TEXT,created_at TEXT NOT NULL);
            """)
    def create_request(self, solicitante_id, specification, max_attempts, max_distractor_attempts=3):
        rid, ts = str(uuid.uuid4()), agora()
        with self._connect() as con:
            con.execute("INSERT INTO requests VALUES(?,?,?,?,?,?,?,?,?,?,?)",(rid,solicitante_id,Estado.REQUESTED.value,
                json.dumps(specification,ensure_ascii=False),max_attempts,max_distractor_attempts,0,0,0,ts,ts))
            self._event(con,rid,None,None,Estado.REQUESTED,"HAILA","solicitação registrada",specification)
        return rid
    def get_request(self, rid):
        with self._connect() as con: row=con.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone()
        if row is None: raise KeyError(f"solicitação não encontrada: {rid}")
        out=dict(row); out["specification"]=json.loads(out.pop("specification_json")); return out
    def increment_attempt(self,rid,kind):
        col={"stem":"stem_attempts","distractor":"distractor_attempts"}.get(kind)
        if not col: raise ValueError("tipo de tentativa inválido")
        with self._connect() as con: con.execute(f"UPDATE requests SET {col}={col}+1,attempts=attempts+1,updated_at=? WHERE id=?",(agora(),rid))
    def save_artifact(self,rid,kind,payload,provenance):
        with self._connect() as con: con.execute("INSERT INTO artifacts(request_id,kind,payload_json,provenance_json,created_at) VALUES(?,?,?,?,?)",
            (rid,kind,json.dumps(payload,ensure_ascii=False),json.dumps(provenance,ensure_ascii=False),agora()))
    def record_flags(self,rid,flags):
        with self._connect() as con:
            for f in flags: con.execute("INSERT INTO red_flags(request_id,code,stage,field,evidence,repair_target,created_at) VALUES(?,?,?,?,?,?,?)",
                (rid,f["codigo"],f["etapa"],f["campo"],f["evidencia"],f["reparo"],agora()))


    def artifacts_by_kind(self, rid, kind):
        """Return decoded artifacts of one kind, oldest first."""
        with self._connect() as con:
            rows = [
                dict(r) for r in con.execute(
                    "SELECT * FROM artifacts WHERE request_id=? AND kind=? ORDER BY id",
                    (rid, kind),
                )
            ]
        for item in rows:
            item["payload"] = json.loads(item.pop("payload_json"))
            item["provenance"] = json.loads(item.pop("provenance_json"))
        return rows

    def latest_artifact(self, rid, kind):
        """Return the newest decoded artifact of one kind, or None."""
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM artifacts WHERE request_id=? AND kind=? ORDER BY id DESC LIMIT 1",
                (rid, kind),
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json"))
        item["provenance"] = json.loads(item.pop("provenance_json"))
        return item

    def save_distractor_pool(self, rid, distractors, provenance=None):
        """Persist the current accepted pool as a checkpoint artifact."""
        payload = [
            d.to_dict() if hasattr(d, "to_dict") else dict(d)
            for d in distractors
        ]
        self.save_artifact(
            rid,
            "DISTRACTOR_POOL_CHECKPOINT",
            payload,
            provenance or {},
        )

    def load_distractor_pool(self, rid):
        """Load the newest accepted distractor pool checkpoint."""
        artifact = self.latest_artifact(rid, "DISTRACTOR_POOL_CHECKPOINT")
        return [] if artifact is None else list(artifact["payload"])

    def add_version(self,rid,question,provenance):
        with self._connect() as con:
            if con.execute("SELECT 1 FROM requests WHERE id=?",(rid,)).fetchone() is None: raise KeyError(rid)
            number=con.execute("SELECT COALESCE(MAX(version_number),0)+1 FROM versions WHERE request_id=?",(rid,)).fetchone()[0]
            vid,ts=str(uuid.uuid4()),agora(); con.execute("INSERT INTO versions VALUES(?,?,?,?,?,?)",(vid,rid,number,json.dumps(question,ensure_ascii=False),json.dumps(provenance,ensure_ascii=False),ts))
        return self.get_version(vid)
    def add_review(self,rid,vid,reviewer_role,reviewer_name,reviewer_kind,decision,audit_percentage,comments="",red_flags=None,model=None):
        review_id,ts=str(uuid.uuid4()),agora()
        with self._connect() as con:
            if con.execute("SELECT 1 FROM versions WHERE id=? AND request_id=?",(vid,rid)).fetchone() is None:
                raise KeyError(f"versão não encontrada para a solicitação: {vid}")
            con.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(
                review_id,rid,vid,reviewer_role,reviewer_name,reviewer_kind,decision,audit_percentage,
                comments,json.dumps(red_flags or [],ensure_ascii=False),model,ts,
            ))
        return self.get_review(review_id)
    def get_review(self,review_id):
        with self._connect() as con: row=con.execute("SELECT * FROM reviews WHERE id=?",(review_id,)).fetchone()
        if row is None: raise KeyError(f"avaliação não encontrada: {review_id}")
        out=dict(row);out["red_flags"]=json.loads(out.pop("red_flags_json"));return out
    def get_version(self,vid):
        with self._connect() as con: row=con.execute("SELECT * FROM versions WHERE id=?",(vid,)).fetchone()
        if row is None: raise KeyError(vid)
        out=dict(row); out["question"]=json.loads(out.pop("question_json")); out["provenance"]=json.loads(out.pop("provenance_json")); return out
    def latest_version(self,rid):
        with self._connect() as con: row=con.execute("SELECT id FROM versions WHERE request_id=? ORDER BY version_number DESC LIMIT 1",(rid,)).fetchone()
        if row is None:
            raise RuntimeError("sem versão")
        return self.get_version(row["id"])
    def transition(self,rid,vid,to_state,component,reason,evidence=None):
        with self._connect() as con:
            row=con.execute("SELECT state FROM requests WHERE id=?",(rid,)).fetchone()
            if row is None: raise KeyError(rid)
            old=Estado(row["state"])
            if to_state not in TRANSICOES_PERMITIDAS.get(old,set()): raise RuntimeError(f"transição inválida: {old.value}->{to_state.value}")
            con.execute("UPDATE requests SET state=?,updated_at=? WHERE id=?",(to_state.value,agora(),rid)); self._event(con,rid,vid,old,to_state,component,reason,evidence)
    def history(self,rid):
        req=self.get_request(rid)
        with self._connect() as con:
            versions=[dict(r) for r in con.execute("SELECT id,version_number,created_at FROM versions WHERE request_id=? ORDER BY version_number",(rid,))]
            events=[dict(r) for r in con.execute("SELECT * FROM events WHERE request_id=? ORDER BY id",(rid,))]
            artifacts=[dict(r) for r in con.execute("SELECT * FROM artifacts WHERE request_id=? ORDER BY id",(rid,))]
            flags=[dict(r) for r in con.execute("SELECT * FROM red_flags WHERE request_id=? ORDER BY id",(rid,))]
            reviews=[dict(r) for r in con.execute("SELECT * FROM reviews WHERE request_id=? ORDER BY created_at",(rid,))]
        for e in events:e["evidence"]=json.loads(e.pop("evidence_json"))
        for a in artifacts:a["payload"]=json.loads(a.pop("payload_json"));a["provenance"]=json.loads(a.pop("provenance_json"))
        for review in reviews:review["red_flags"]=json.loads(review.pop("red_flags_json"))
        latest=self.get_version(versions[-1]["id"]) if versions else None
        quality_trace=_quality_trace(req,artifacts,flags,events)
        return {"request":req,"versions":versions,"latest_version":latest,"artifacts":artifacts,"red_flags":flags,"events":events,"reviews":reviews,"quality_trace":quality_trace}
    @staticmethod
    def _event(con,rid,vid,old,new,component,reason,evidence): con.execute("INSERT INTO events(request_id,version_id,from_state,to_state,component,reason,evidence_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (rid,vid,old.value if old else None,new.value,component,reason,json.dumps(evidence or {},ensure_ascii=False),agora()))
