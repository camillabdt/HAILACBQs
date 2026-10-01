#!/usr/bin/env python3
"""Executa C1-C3 com retomada, pausa e repetição de falhas temporárias."""
from __future__ import annotations
import argparse,json,os,sys,time,urllib.error,urllib.request
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"backend"))
from haila.ablation import AblationCondition,run_condition
from haila.generator import BestOfNDistractorGenerator,DeterministicPoolSelector,QwenDistractorGenerator,stem_generator_from_env
from haila.rag import rag_from_env

def http_call(base_url,condition,specification,seed,timeout=900):
    body=json.dumps({"condition":condition.value,"specification":specification,"seed":seed},ensure_ascii=False).encode()
    req=urllib.request.Request(base_url.rstrip('/')+'/evaluations/ablation/run',data=body,method='POST',headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response:return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raw=exc.read().decode(errors='replace')
        try: detail=json.loads(raw).get('detail',raw)
        except json.JSONDecodeError: detail=raw
        error=RuntimeError(f"HTTP {exc.code}: {detail}"); error.status_code=exc.code; raise error from exc

def with_retry(call,max_retries,retry_wait):
    attempt=0
    while True:
        attempt+=1
        try:return call(),attempt
        except Exception as exc:
            temporary=getattr(exc,'status_code',None) in {429,502,503,504}
            if not temporary or attempt>max_retries:raise
            print(json.dumps({'status':'WAITING_TO_RETRY','attempt':attempt,'wait_seconds':retry_wait,'error':str(exc)},ensure_ascii=False),flush=True)
            time.sleep(retry_wait)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--conditions',nargs='+',choices=[x.value for x in AblationCondition],required=True); ap.add_argument('--specs',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); ap.add_argument('--base-url'); ap.add_argument('--resume',action='store_true'); ap.add_argument('--delay-seconds',type=float,default=15.0); ap.add_argument('--max-retries',type=int,default=5); ap.add_argument('--retry-wait-seconds',type=float,default=60.0); args=ap.parse_args()
    specs=[json.loads(x) for x in args.specs.read_text(encoding='utf-8').splitlines() if x.strip()]
    stem=None if args.base_url else stem_generator_from_env(); rag=None if args.base_url else rag_from_env(); slm=None
    if args.resume and args.out.exists():
        run=json.loads(args.out.read_text(encoding='utf-8')); run.setdefault('resumed_at',[]).append(datetime.now(timezone.utc).isoformat())
    else:run={'started_at':datetime.now(timezone.utc).isoformat(),'conditions':args.conditions,'items':[]}
    completed={(x.get('condition'),x.get('spec_id')) for x in run['items'] if x.get('state')=='COMPLETED'}
    selected={(c,s['spec_id']) for c in args.conditions for s in specs}
    run['items']=[x for x in run['items'] if x.get('state')=='COMPLETED' or (x.get('condition'),x.get('spec_id')) not in selected]
    for condition_name in args.conditions:
        condition=AblationCondition(condition_name)
        if condition is AblationCondition.C3_RAG_LLM_SLM and slm is None and not args.base_url:
            base=os.getenv('HAILA_SLM_BASE_MODEL','Qwen/Qwen2.5-1.5B-Instruct'); adapter=os.getenv('HAILA_SLM_ADAPTER_PATH','').strip() or None
            slm=BestOfNDistractorGenerator(QwenDistractorGenerator(base,adapter),DeterministicPoolSelector())
        for spec in specs:
            sid=spec['spec_id']
            if (condition.value,sid) in completed:
                print(json.dumps({'condition':condition.value,'spec_id':sid,'state':'SKIPPED_COMPLETED'}),flush=True); continue
            payload={k:v for k,v in spec.items() if k!='spec_id'}; started=time.perf_counter(); attempts=0
            try:
                if args.base_url: result,attempts=with_retry(lambda:http_call(args.base_url,condition,payload,f'{condition.value}:{sid}'),args.max_retries,args.retry_wait_seconds)
                else: result,attempts=with_retry(lambda:run_condition(condition,payload,llm_call=stem.caller,model=stem.model,rag=rag,stem_generator=stem,distractor_generator=slm,seed=f'{condition.value}:{sid}'),args.max_retries,args.retry_wait_seconds)
            except Exception as exc:result={'condition':condition.value,'state':'FAILED','error_type':type(exc).__name__,'error':str(exc)}
            result['execution_attempts']=attempts; result['elapsed_with_retries_seconds']=round(time.perf_counter()-started,3)
            run['items'].append({'spec_id':sid,**result}); args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(json.dumps(run,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({'condition':condition.value,'spec_id':sid,'state':result['state'],'seconds':result.get('elapsed_seconds'),'attempts':attempts,'error':result.get('error')},ensure_ascii=False),flush=True)
            if args.delay_seconds>0:time.sleep(args.delay_seconds)
    run['finished_at']=datetime.now(timezone.utc).isoformat(); args.out.write_text(json.dumps(run,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
