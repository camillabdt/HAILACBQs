#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, json, statistics, time, urllib.error, urllib.request
from collections import Counter
from pathlib import Path

BASE = "http://127.0.0.1:8000"
ROOT = Path.home() / "HAILA"
OUT = ROOT / "evaluation" / "results" / "experimento-100-pareado-jev"

AREAS = [
    ("Banco de Dados","Transações e isolamento","Distinguir anomalias de isolamento em um cenário de transações concorrentes.","Analisar mecanismos de controle de concorrência em bancos de dados.","Identificar a anomalia de isolamento a partir de uma situação-problema.","Transações, isolamento e controle de concorrência.",[]),
    ("Engenharia de Software","Engenharia de requisitos","Classificar corretamente requisitos funcionais e não funcionais em um cenário de software.","Analisar especificações de requisitos de software.","Classificar requisitos a partir de uma situação-problema.","Requisitos funcionais e não funcionais.",[]),
    ("Redes de Computadores","IPv4 e subnetting","Calcular e selecionar o prefixo IPv4 adequado para uma necessidade de hosts ou subdivisão de rede.","Analisar princípios de endereçamento em redes de computadores.","Aplicar CIDR e subnetting em uma situação-problema.","Endereçamento IPv4, CIDR e subnetting.",["Avaliar somente subnetting; não combinar com roteamento, NAT, DHCP ou VLAN.","O gabarito deve ser apenas um prefixo CIDR (/xx) ou uma máscara decimal IPv4 válida."]),
    ("Sistemas Operacionais","Memória virtual","Distinguir estruturas e mecanismos de tradução de endereços em memória virtual.","Analisar mecanismos de gerenciamento de memória em sistemas operacionais.","Relacionar paginação, tabela de páginas e TLB ao cenário apresentado.","Memória virtual, paginação e TLB.",[]),
    ("Algoritmos e Estruturas de Dados","Busca em grafos","Selecionar a estratégia de busca em grafos adequada às propriedades do problema apresentado.","Analisar algoritmos aplicados a estruturas de grafos.","Distinguir busca em largura e busca em profundidade em uma situação-problema.","Grafos, BFS e DFS.",[]),
    ("Segurança da Informação","Criptografia","Distinguir objetivos e usos de hash, criptografia simétrica e criptografia assimétrica.","Analisar mecanismos básicos de segurança da informação.","Selecionar o mecanismo criptográfico adequado ao objetivo apresentado.","Hash e criptografia simétrica e assimétrica.",[]),
    ("Inteligência Artificial","Paradigmas de aprendizado","Distinguir aprendizado supervisionado, não supervisionado e por reforço a partir de um cenário.","Analisar técnicas fundamentais de inteligência artificial.","Classificar o paradigma de aprendizado adequado ao cenário.","Aprendizado supervisionado, não supervisionado e por reforço.",[]),
    ("Sistemas Distribuídos","Transações distribuídas","Distinguir mecanismos de coordenação de transações distribuídas em um cenário.","Analisar mecanismos de consistência e coordenação em sistemas distribuídos.","Relacionar 2PC, SAGA e alternativas de coordenação ao problema apresentado.","Transações distribuídas, 2PC e SAGA.",[]),
    ("Arquitetura de Computadores","Memória cache","Analisar o efeito da localidade de acesso sobre o comportamento da memória cache.","Analisar a hierarquia de memória de sistemas computacionais.","Relacionar localidade temporal e espacial ao desempenho de cache.","Hierarquia de memória, cache e localidade.",[]),
    ("Compiladores e Linguagens","Fases de compilação","Distinguir análise léxica, sintática e semântica a partir de um erro ou tarefa de compilação.","Analisar etapas do processamento de linguagens de programação.","Relacionar um problema à fase adequada do compilador.","Análise léxica, sintática e semântica.",[]),
    ("Interação Humano-Computador","Usabilidade","Selecionar um princípio de usabilidade adequado diante de um problema de interação.","Analisar qualidade de interação em interfaces computacionais.","Relacionar problemas de interface a princípios de usabilidade.","Usabilidade e avaliação de interfaces.",[]),
    ("Teoria da Computação","Autômatos e linguagens","Relacionar modelos de autômatos às classes de linguagens que reconhecem.","Analisar fundamentos formais da computação.","Distinguir modelos de reconhecimento de linguagens formais.","Autômatos finitos e linguagens formais.",[]),
]

CRITERIA = ("gabarito_unico","enunciado_claro","alinhamento_pedagogico","distratores_plausiveis","sem_ambiguidade")

class HttpFailure(RuntimeError):
    def __init__(self,status,path,body,retry_after=None):
        super().__init__(f"HTTP {status} em {path}: {body}")
        self.status=status; self.retry_after=retry_after

def http_json(method,path,payload=None,timeout=1800):
    data=None; headers={"Accept":"application/json"}
    if payload is not None:
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8")
        headers["Content-Type"]="application/json"
    req=urllib.request.Request(BASE+path,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as resp:
            raw=resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body=exc.read().decode("utf-8",errors="replace")
        raise HttpFailure(exc.code,path,body,exc.headers.get("Retry-After")) from exc

def append_jsonl(path,obj):
    with path.open("a",encoding="utf-8") as f:
        f.write(json.dumps(obj,ensure_ascii=False)+"\n")

def read_jsonl(path):
    if not path.exists(): return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]

def cases_100():
    counts=Counter(); out=[]
    for i in range(100):
        area=AREAS[i % len(AREAS)]
        counts[area[0]] += 1
        out.append({
            "case_id":f"Q{i+1:03d}","area":area[0],"subtema":area[1],
            "objetivo":area[2],"competencia":area[3],"habilidade":area[4],
            "objeto":area[5],"extras":area[6],"repetition":counts[area[0]]
        })
    return out

def payload_for(c):
    r=[
        "Gerar uma questão contextualizada e autocontida.",
        "Avaliar uma única decisão principal.",
        "Manter somente uma alternativa defensável como correta.",
        "Produzir quatro distratores plausíveis e do mesmo nível conceitual do gabarito.",
        "Evitar pistas lexicais, alternativas absurdas e formulações ambíguas.",
    ] + c["extras"]
    return {
        "solicitante_id":f"exp100-{c['case_id']}","curso":"Computação","exame":"ENADE",
        "componente":"ESPECIFICO","objetivo_pedagogico":c["objetivo"],"dificuldade":3,
        "competencia":c["competencia"],"habilidade":c["habilidade"],
        "objeto_conhecimento":c["objeto"],"restricoes":r,
        "max_tentativas":3,"max_tentativas_distratores":3,
    }

def last_artifact(history,kind):
    xs=[a for a in history.get("artifacts",[]) if a.get("kind")==kind]
    return xs[-1] if xs else None

def token_usage(history):
    gi=go=gt=li=lo=lt=0
    for a in history.get("artifacts",[]):
        p=a.get("provenance") or {}
        ru=p.get("token_usage_remote") or {}
        lu=p.get("token_usage_local") or {}
        gi+=int(ru.get("prompt_tokens") or 0); go+=int(ru.get("completion_tokens") or 0); gt+=int(ru.get("total_tokens") or 0)
        li+=int(lu.get("input_tokens") or 0); lo+=int(lu.get("output_tokens") or 0); lt+=int(lu.get("total_tokens") or 0)
    return dict(groq_prompt_tokens=gi,groq_completion_tokens=go,groq_total_tokens=gt,slm_input_tokens=li,slm_output_tokens=lo,slm_total_tokens=lt)

def route_info(history):
    a=last_artifact(history,"DISTRACTORS")
    if not a: return dict(route="",distractor_model="",strategy="")
    p=a.get("provenance") or {}; model=str(p.get("modelo") or "")
    if model.startswith("slm-memory-curated"): route="memoria_curada"
    elif model.startswith("deterministic-"): route="deterministico"
    elif "qwen" in model.casefold(): route="qwen_lora"
    else: route="outro"
    return dict(route=route,distractor_model=model,strategy=str(p.get("estrategia") or ""))

def wait_from(exc,fallback=65.0):
    try: return max(1.0,float(exc.retry_after))
    except Exception: return fallback

def generate_retry(rid,max_retries):
    retries=0; waited=0.0
    while True:
        try:
            return http_json("POST",f"/requests/{rid}/generate",timeout=1800),retries,waited
        except HttpFailure as exc:
            if exc.status==429 and retries<max_retries:
                retries+=1; w=wait_from(exc); waited+=w
                print(f"⚠️ Groq 429; aguardando {w:.0f}s ({retries}/{max_retries})")
                time.sleep(w); continue
            raise

def jev_retry(payload,max_retries):
    retries=0; waited=0.0
    while True:
        try:
            return http_json("POST","/evaluations/jev",payload,timeout=120),retries,waited
        except HttpFailure as exc:
            if exc.status in {429,529} and retries<max_retries:
                retries+=1; w=wait_from(exc,min(60.0,2**retries)); waited+=w
                print(f"⚠️ Jev {exc.status}; aguardando {w:.0f}s ({retries}/{max_retries})")
                time.sleep(w); continue
            raise

def export_csv(rows,path,exclude=()):
    flat=[{k:v for k,v in r.items() if k not in exclude} for r in rows]
    if not flat: return
    fields=[]
    for row in flat:
        for k in row:
            if k not in fields: fields.append(k)
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(flat)

def phase_baseline(args):
    s=http_json("GET","/settings/jev",timeout=20)
    if s.get("enabled"):
        raise SystemExit("❌ Baseline exige Jev desligado. Defina HAILA_JEV_ENABLED=0 e reinicie o backend.")
    OUT.mkdir(parents=True,exist_ok=True)
    progress=OUT/"baseline.jsonl"
    done={r["case_id"] for r in read_jsonl(progress)}
    print("FASE 1 — 100 QUESTÕES HAILA SEM JEV")
    print("Já concluídas:",len(done),"| saída:",OUT)
    print("Pode usar Ctrl+C; depois rode o mesmo comando para continuar.")

    for idx,c in enumerate(cases_100(),1):
        if c["case_id"] in done: continue
        print(f"\n[{idx}/100] {c['case_id']} | {c['area']} | repetição {c['repetition']}")
        payload=payload_for(c); started=time.perf_counter(); rid=None
        try:
            created=http_json("POST","/requests",payload,timeout=30); rid=created["id"]
            generated,retries,waited=generate_retry(rid,args.max_429_retries)
            history=http_json("GET",f"/requests/{rid}",timeout=30)
            req=history.get("request") or {}; latest=history.get("latest_version") or {}
            ref=last_artifact(history,"REFERENCE")
            row={
                "case_id":c["case_id"],"area":c["area"],"subtema":c["subtema"],"repetition":c["repetition"],
                "request_id":rid,"specification":payload,"state":generated.get("state"),
                "wall_seconds":round(time.perf_counter()-started,4),
                "provider_retries":retries,"provider_wait_seconds":round(waited,4),
                "attempts":req.get("attempts"),"stem_attempts":req.get("stem_attempts"),
                "distractor_attempts":req.get("distractor_attempts"),
                "historical_red_flags":len(history.get("red_flags") or []),
                "final_red_flags":len(generated.get("red_flags") or []),
                "question":latest.get("question"),"reference":(ref or {}).get("payload") or {},
                **route_info(history),**token_usage(history),
            }
        except Exception as exc:
            row={"case_id":c["case_id"],"area":c["area"],"subtema":c["subtema"],"repetition":c["repetition"],
                 "request_id":rid,"specification":payload,"state":"ERROR",
                 "wall_seconds":round(time.perf_counter()-started,4),
                 "error":f"{type(exc).__name__}: {exc}","question":None,"reference":{}}
        append_jsonl(progress,row); done.add(c["case_id"])
        print("state=",row.get("state"),"| wall=",row.get("wall_seconds"),"| route=",row.get("route","-"),"| flags=",row.get("final_red_flags","-"))
        if len(done)<100 and args.delay>0: time.sleep(args.delay)

    rows=read_jsonl(progress)
    export_csv(rows,OUT/"baseline_metricas.csv",exclude=("specification","question","reference"))
    completed=[r for r in rows if r.get("state")=="GENERATION_COMPLETED"]
    summary={
        "n_total":len(rows),"n_completed":len(completed),
        "completion_rate":len(completed)/len(rows) if rows else 0,
        "mean_wall_seconds":statistics.mean([r["wall_seconds"] for r in completed]) if completed else None,
        "median_wall_seconds":statistics.median([r["wall_seconds"] for r in completed]) if completed else None,
        "groq_tokens_total":sum(int(r.get("groq_total_tokens") or 0) for r in rows),
        "slm_tokens_total":sum(int(r.get("slm_total_tokens") or 0) for r in rows),
        "route_counts":dict(Counter(r.get("route") for r in completed if r.get("route"))),
    }
    (OUT/"baseline_resumo.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print("\n✅ Baseline concluída:",json.dumps(summary,ensure_ascii=False,indent=2))

def phase_jev(args):
    s=http_json("GET","/settings/jev",timeout=20)
    if not s.get("enabled") or not s.get("configured"):
        raise SystemExit("❌ Fase Jev exige enabled=true e configured=true.")
    if s.get("mode")!="shadow":
        raise SystemExit("❌ Use HAILA_JEV_MODE=shadow nesta fase.")

    baseline=read_jsonl(OUT/"baseline.jsonl")
    if not baseline: raise SystemExit("❌ Rode --phase baseline primeiro.")
    eligible=[r for r in baseline if r.get("state")=="GENERATION_COMPLETED" and r.get("question")]
    progress=OUT/"jev.jsonl"; done={r["case_id"] for r in read_jsonl(progress)}

    print("FASE 2 — AS MESMAS QUESTÕES AVALIADAS PELO JEV")
    print("Elegíveis:",len(eligible),"| já avaliadas:",len(done))
    print("Pode usar Ctrl+C; depois rode o mesmo comando para continuar.")

    for idx,b in enumerate(eligible,1):
        if b["case_id"] in done: continue
        print(f"\n[{idx}/{len(eligible)}] {b['case_id']} | {b['area']}")
        payload={"question":b["question"],"specification":b.get("specification") or {},"reference":b.get("reference") or {}}
        started=time.perf_counter()
        try:
            response,retries,waited=jev_retry(payload,args.max_jev_retries)
            result=response.get("result") or {}; prov=response.get("provenance") or {}; criteria=result.get("criteria") or {}
            row={
                "case_id":b["case_id"],"area":b["area"],"request_id":b["request_id"],"status":"OK",
                "jev_wall_seconds":round(time.perf_counter()-started,4),
                "jev_retries":retries,"jev_wait_seconds":round(waited,4),
                "model_requested":prov.get("model_requested"),"model_resolved":prov.get("model_resolved"),
                "latency_ms":prov.get("latency_ms"),
                "input_tokens":(prov.get("usage") or {}).get("input_tokens"),
                "output_tokens":(prov.get("usage") or {}).get("output_tokens"),
                "estimated_cost_usd":prov.get("estimated_cost_usd"),
                "minimum_probability":result.get("minimum_probability"),
                "mean_probability":result.get("mean_probability"),
                "lowest_criterion":result.get("lowest_criterion"),
                "requires_human_review":result.get("requires_human_review"),
            }
            for k in CRITERIA: row[k]=(criteria.get(k) or {}).get("probability_yes")
        except Exception as exc:
            row={"case_id":b["case_id"],"area":b["area"],"request_id":b["request_id"],"status":"ERROR",
                 "jev_wall_seconds":round(time.perf_counter()-started,4),"error":f"{type(exc).__name__}: {exc}"}
        append_jsonl(progress,row); done.add(b["case_id"])
        print("status=",row.get("status"),"| min=",row.get("minimum_probability"),"| lowest=",row.get("lowest_criterion"),"| latency_ms=",row.get("latency_ms"))
        if len(done)<len(eligible) and args.jev_delay>0: time.sleep(args.jev_delay)

    rows=read_jsonl(progress); export_csv(rows,OUT/"jev_metricas.csv")
    ok=[r for r in rows if r.get("status")=="OK"]
    summary={
        "n_total":len(rows),"n_ok":len(ok),
        "mean_latency_ms":statistics.mean([float(r["latency_ms"]) for r in ok if r.get("latency_ms") is not None]) if ok else None,
        "total_cost_usd":sum(float(r.get("estimated_cost_usd") or 0) for r in ok),
        "criterion_means":{k:(statistics.mean([float(r[k]) for r in ok if r.get(k) is not None]) if any(r.get(k) is not None for r in ok) else None) for k in CRITERIA},
        "lowest_criterion_counts":dict(Counter(r.get("lowest_criterion") for r in ok if r.get("lowest_criterion"))),
    }
    (OUT/"jev_resumo.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print("\n✅ Jev concluído:",json.dumps(summary,ensure_ascii=False,indent=2))

def phase_compare():
    b=read_jsonl(OUT/"baseline.jsonl"); j=read_jsonl(OUT/"jev.jsonl")
    if not b or not j: raise SystemExit("❌ Rode baseline e jev antes.")
    jm={r["case_id"]:r for r in j}
    paired=[]
    for x in b:
        if x.get("state")!="GENERATION_COMPLETED": continue
        y=jm.get(x["case_id"])
        if not y or y.get("status")!="OK": continue
        js=float(y.get("latency_ms") or 0)/1000
        row={
            "case_id":x["case_id"],"area":x["area"],"request_id":x["request_id"],
            "haila_sem_jev_seconds":x["wall_seconds"],"jev_latency_seconds":round(js,6),
            "haila_mais_jev_estimated_seconds":round(float(x["wall_seconds"])+js,6),
            "jev_cost_usd":y.get("estimated_cost_usd"),
            "jev_minimum_probability":y.get("minimum_probability"),
            "jev_mean_probability":y.get("mean_probability"),
            "jev_lowest_criterion":y.get("lowest_criterion"),
        }
        for k in CRITERIA: row[f"jev_{k}"]=y.get(k)
        paired.append(row)

    export_csv(paired,OUT/"comparacao_pareada.csv")
    bt=[float(r["haila_sem_jev_seconds"]) for r in paired]
    jt=[float(r["jev_latency_seconds"]) for r in paired]
    ct=[float(r["haila_mais_jev_estimated_seconds"]) for r in paired]
    summary={
        "design":"pareado: mesmas questões sem Jev e depois avaliadas pelo Jev em shadow",
        "n_pairs":len(paired),
        "mean_haila_sem_jev_seconds":statistics.mean(bt),
        "mean_jev_latency_seconds":statistics.mean(jt),
        "mean_haila_mais_jev_seconds":statistics.mean(ct),
        "mean_overhead_percent":statistics.mean(jt)/statistics.mean(bt)*100 if statistics.mean(bt) else None,
        "jev_total_cost_usd":sum(float(r.get("jev_cost_usd") or 0) for r in paired),
        "criterion_means":{k:statistics.mean([float(r[f"jev_{k}"]) for r in paired if r.get(f"jev_{k}") is not None]) for k in CRITERIA},
        "lowest_criterion_counts":dict(Counter(r.get("jev_lowest_criterion") for r in paired if r.get("jev_lowest_criterion"))),
        "important_note":"Como o Jev está em shadow, ele não altera a questão. Esta etapa mede overhead e informação semântica adicional, não melhoria causal da qualidade.",
    }
    (OUT/"comparacao_resumo.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    report=f"""# Experimento pareado HAILA × HAILA+Jev

- Pares válidos: {summary['n_pairs']}
- Tempo médio HAILA sem Jev: {summary['mean_haila_sem_jev_seconds']:.3f} s
- Latência média Jev: {summary['mean_jev_latency_seconds']:.3f} s
- Tempo estimado HAILA+Jev: {summary['mean_haila_mais_jev_seconds']:.3f} s
- Overhead médio: {summary['mean_overhead_percent']:.2f}%
- Custo total Jev: US$ {summary['jev_total_cost_usd']:.6f}

## Médias por critério Jev
"""
    for k,v in summary["criterion_means"].items(): report+=f"- {k}: {v:.4f}\n"
    report+="\n## Critério mais fraco\n"
    for k,v in summary["lowest_criterion_counts"].items(): report+=f"- {k}: {v}\n"
    report+="\n## Nota metodológica\nO Jev foi usado em modo shadow. Portanto, ele não bloqueou nem regenerou itens. Usamos as mesmas 100 questões antes e depois da avaliação Jev para não confundir aleatoriedade da geração com efeito do avaliador.\n"
    (OUT/"RELATORIO.md").write_text(report,encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print("\nArquivos em:",OUT)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--phase",choices=["baseline","jev","compare"],required=True)
    ap.add_argument("--delay",type=float,default=45.0)
    ap.add_argument("--jev-delay",type=float,default=1.0)
    ap.add_argument("--max-429-retries",type=int,default=3)
    ap.add_argument("--max-jev-retries",type=int,default=3)
    args=ap.parse_args()
    if args.phase=="baseline": phase_baseline(args)
    elif args.phase=="jev": phase_jev(args)
    else: phase_compare()

if __name__=="__main__":
    main()
