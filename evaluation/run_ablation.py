#!/usr/bin/env python3
"""Executa C1-C3; C4 permanece no executor oficial da arquitetura."""
from __future__ import annotations
import argparse,json,os,sys,urllib.error,urllib.request
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"backend"))
from haila.ablation import AblationCondition,run_condition
from haila.generator import BestOfNDistractorGenerator,DeterministicPoolSelector,QwenDistractorGenerator,stem_generator_from_env
from haila.rag import rag_from_env

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--conditions',nargs='+',choices=[x.value for x in AblationCondition],required=True); ap.add_argument('--specs',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); ap.add_argument('--base-url'); args=ap.parse_args()
    specs=[json.loads(x) for x in args.specs.read_text(encoding='utf-8').splitlines() if x.strip()]
    stem=None if args.base_url else stem_generator_from_env(); rag=None if args.base_url else rag_from_env(); slm=None
    run={'started_at':datetime.now(timezone.utc).isoformat(),'conditions':args.conditions,'items':[]}
    for condition_name in args.conditions:
        condition=AblationCondition(condition_name)
        if condition is AblationCondition.C3_RAG_LLM_SLM and slm is None:
            base=os.getenv('HAILA_SLM_BASE_MODEL','Qwen/Qwen2.5-1.5B-Instruct'); adapter=os.getenv('HAILA_SLM_ADAPTER_PATH','').strip() or None
            slm=BestOfNDistractorGenerator(QwenDistractorGenerator(base,adapter),DeterministicPoolSelector())
        for spec in specs:
            sid=spec['spec_id']; payload={k:v for k,v in spec.items() if k!='spec_id'}
            try:
                if args.base_url:
                    body=json.dumps({'condition':condition.value,'specification':payload,'seed':f'{condition.value}:{sid}'},ensure_ascii=False).encode()
                    req=urllib.request.Request(args.base_url.rstrip('/')+'/evaluations/ablation/run',data=body,method='POST',headers={'Content-Type':'application/json'})
                    with urllib.request.urlopen(req,timeout=900) as response: result=json.loads(response.read())
                else:
                    result=run_condition(condition,payload,llm_call=stem.caller,model=stem.model,rag=rag,stem_generator=stem,distractor_generator=slm,seed=f'{condition.value}:{sid}')
            except Exception as exc: result={'condition':condition.value,'state':'FAILED','error_type':type(exc).__name__,'error':str(exc)}
            run['items'].append({'spec_id':sid,**result}); args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(json.dumps(run,ensure_ascii=False,indent=2)+'\n')
            print(json.dumps({'condition':condition.value,'spec_id':sid,'state':result['state'],'seconds':result.get('elapsed_seconds')},ensure_ascii=False),flush=True)
    run['finished_at']=datetime.now(timezone.utc).isoformat(); args.out.write_text(json.dumps(run,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__': main()
