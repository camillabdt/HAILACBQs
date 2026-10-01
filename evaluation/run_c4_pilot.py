#!/usr/bin/env python3
"""Executa a condição C4 pela API ativa e preserva evidência bruta."""
from __future__ import annotations
import argparse, json, sqlite3, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def call(method,url,payload=None,timeout=900):
    body=None if payload is None else json.dumps(payload,ensure_ascii=False).encode()
    req=urllib.request.Request(url,data=body,method=method,headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response:
            return response.status,json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raw=exc.read().decode(errors="replace")
        try: data=json.loads(raw)
        except json.JSONDecodeError: data={"detail":raw}
        return exc.code,data

def call_with_retry(method,url,payload,max_retries,retry_wait,timeout=900):
    attempts=0
    while True:
        attempts+=1; status,data=call(method,url,payload,timeout)
        if status not in {429,502,503,504} or attempts>max_retries:return status,data,attempts
        print(json.dumps({"status":"WAITING_TO_RETRY","attempt":attempts,"wait_seconds":retry_wait,"http_status":status,"detail":data.get("detail")},ensure_ascii=False),flush=True)
        time.sleep(retry_wait)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--base-url",default="http://127.0.0.1:8010"); ap.add_argument("--specs",type=Path,default=ROOT/"evaluation/pilot_specifications.jsonl"); ap.add_argument("--out",type=Path,default=ROOT/"evaluation/results/c4_pilot_raw.json"); ap.add_argument("--db",type=Path,default=ROOT/"runtime/haila.sqlite3"); ap.add_argument("--run-id",default="baseline"); ap.add_argument("--resume",action="store_true"); ap.add_argument("--delay-seconds",type=float,default=15.0); ap.add_argument("--max-retries",type=int,default=5); ap.add_argument("--retry-wait-seconds",type=float,default=60.0); args=ap.parse_args()
    specs=[json.loads(x) for x in args.specs.read_text(encoding="utf-8").splitlines() if x.strip()]
    if args.resume and args.out.exists():
        run=json.loads(args.out.read_text(encoding="utf-8")); run.setdefault("resumed_at",[]).append(datetime.now(timezone.utc).isoformat())
    else:
        run={"condition":"C4","run_id":args.run_id,"started_at":datetime.now(timezone.utc).isoformat(),"base_url":args.base_url,"items":[]}
    completed_specs={item.get("spec_id") for item in run.get("items",[])}
    for index,spec in enumerate(specs,1):
        payload=dict(spec); spec_id=payload.pop("spec_id"); requester=f"evaluation-{args.run_id}-{spec_id}"; payload.update(solicitante_id=requester,max_tentativas=3,max_tentativas_distratores=3)
        if spec_id in completed_specs:
            print(json.dumps({"progress":f"{index}/{len(specs)}","spec_id":spec_id,"state":"SKIPPED_RECORDED"},ensure_ascii=False),flush=True); continue
        started=time.perf_counter()
        con=sqlite3.connect(args.db); existing=con.execute("SELECT id,state FROM requests WHERE solicitante_id=? ORDER BY created_at DESC LIMIT 1",(requester,)).fetchone(); con.close()
        if existing and existing[1] == "REQUESTED":
            create_status,created=200,{"id":existing[0],"resumed":True}
        else:
            create_status,created=call("POST",args.base_url+"/requests",payload)
        item={"spec_id":spec_id,"specification":spec,"create_status":create_status,"created":created}
        if create_status in (200,201):
            rid=created.get("request_id") or created["id"]; gen_status,generated,attempts=call_with_retry("POST",f"{args.base_url}/requests/{rid}/generate",None,args.max_retries,args.retry_wait_seconds)
            _,history=call("GET",f"{args.base_url}/requests/{rid}")
            item.update(request_id=rid,generation_status=gen_status,generation=generated,history=history,generation_attempts=attempts)
        item["elapsed_seconds"]=round(time.perf_counter()-started,3); run["items"].append(item)
        args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(json.dumps(run,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({"progress":f"{index}/{len(specs)}","spec_id":spec_id,"state":item.get("generation",{}).get("state"),"seconds":item["elapsed_seconds"]},ensure_ascii=False),flush=True)
        if args.delay_seconds>0: time.sleep(args.delay_seconds)
    run["finished_at"]=datetime.now(timezone.utc).isoformat(); args.out.write_text(json.dumps(run,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__": main()
