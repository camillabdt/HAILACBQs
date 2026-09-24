#!/usr/bin/env python3
"""Benchmarks automáticos dos componentes da HAILA, sem avaliação humana."""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))

from haila.contracts import DistratorGerado, NucleoQuestao
from haila.hybrid import MemoriaDistratoresCurados, TAXONOMIAS_CURADAS
from haila.rag import CorpusJsonlRAG
from haila.redflags import DeterministicRedFlagAnalyzer
from haila.structural import avaliar_distratores, avaliar_item, avaliar_nucleo


def main():
    results=[]
    def record(group,name,passed,evidence):
        results.append({"grupo":group,"teste":name,"passou":bool(passed),"evidencia":evidence})

    # RAG: cada registro é consultado por seus próprios metadados, sem usar o texto-base.
    corpus=ROOT/"backend/fontes_rag.jsonl"
    entries=[json.loads(x) for x in corpus.read_text(encoding="utf-8").splitlines() if x.strip()]
    rag=CorpusJsonlRAG(corpus)
    for entry in entries:
        spec={"objetivo_pedagogico":entry["habilidade"],"objeto_conhecimento":entry["objeto_conhecimento"],"curso":"Computação"}
        got=rag(spec)
        record("RAG",entry["id"],got.id==entry["id"],f"esperado={entry['id']}; recuperado={got.id}")

    # Memória: cada termo conhecido deve recuperar quatro alternativas distintas sem copiar o alvo.
    memory=MemoriaDistratoresCurados(dataset=ROOT/"evaluation/__dataset_inexistente__.jsonl")
    for idx,group in enumerate(TAXONOMIAS_CURADAS):
        for answer in group:
            recovered=memory.recuperar(answer)
            ok=recovered is not None
            evidence="sem recuperação"
            if recovered:
                ds,_=recovered; texts=[d.texto.casefold() for d in ds]
                ok=len(ds)==4 and len(set(texts))==4 and answer.casefold() not in texts
                evidence=f"alvo={answer}; distratores={[d.texto for d in ds]}"
            record("SLM_MEMORIA",f"familia_{idx}:{answer}",ok,evidence)

    clean={"enunciado":"Considere um cenário suficientemente descrito e selecione a alternativa correta.","alternativas":["A","B","C","D","E"],"correta":0,"tem_imagem":False}
    analyzer=DeterministicRedFlagAnalyzer()
    cases=[
        ("item_limpo",clean,set()),
        ("placeholder",dict(clean,alternativas=["A","<NAME>","C","D","E"]),{"placeholder_residual"}),
        ("imagem_ausente",dict(clean,tem_imagem=True),{"dependencia_visual_ausente"}),
        ("vazamento",dict(clean,enunciado="Questão baseada no cartão-resposta do exame."),{"vazamento_de_artefato"}),
        ("alternativa_vazia",dict(clean,alternativas=["A","B","","D","E"]),{"formatacao_quebrada"}),
    ]
    for name,q,expected in cases:
        found={f.codigo for f in analyzer(q,{},None)[0]}
        record("RED_FLAGS_ITEM",name,expected<=found and (bool(expected) or not found),f"esperado={sorted(expected)}; encontrado={sorted(found)}")

    nuclei=[
        ("plural_singular",NucleoQuestao("Quais propriedades são demonstradas no cenário suficientemente detalhado?","Atomicidade","Explicação","C","H","O"),"enunciado_ambiguo"),
        ("binario",NucleoQuestao("Classifique o requisito como funcional ou não funcional no cenário apresentado.","Não funcional","Explicação","C","H","O"),"espaco_de_respostas_binario"),
        ("protocolo",NucleoQuestao("Dado o cenário detalhado, qual protocolo deve ser escolhido?","TCP","Explicação","C","H","O"),"selecao_de_protocolo_potencialmente_ambigua"),
    ]
    for name,n,expected in nuclei:
        found={f.codigo for f in avaliar_nucleo(n)}
        record("RED_FLAGS_NUCLEO",name,expected in found,f"esperado={expected}; encontrado={sorted(found)}")

    n=NucleoQuestao("Qual propriedade responde corretamente ao cenário suficientemente descrito?","Atomicidade","Explicação","C","H","O")
    duplicate=[DistratorGerado("Isolamento"),DistratorGerado("Durabilidade"),DistratorGerado("Consistência"),DistratorGerado("Isolamento")]
    found={f.codigo for f in avaliar_distratores(n,duplicate)}
    record("RED_FLAGS_DISTRACTORES","duplicidade","distratores_duplicados" in found,f"encontrado={sorted(found)}")
    found={f.codigo for f in avaliar_item({"alternativas":["A","B","C"],"correta":7})}
    record("RED_FLAGS_ESTRUTURA","item_malformado",{"quantidade_alternativas_invalida","gabarito_estruturalmente_invalido"}<=found,f"encontrado={sorted(found)}")

    groups={}
    for r in results:
        g=groups.setdefault(r["grupo"],{"total":0,"passou":0})
        g["total"]+=1; g["passou"]+=int(r["passou"])
    report={"metodo":"haila-component-benchmark-v1","resumo":{"total":len(results),"passou":sum(r["passou"] for r in results),"falhou":sum(not r["passou"] for r in results),"grupos":groups},"resultados":results}
    out=ROOT/"evaluation/results/component_benchmark.json"; out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=["# Benchmark automático dos componentes","","> Avaliação técnica automática; não substitui julgamento pedagógico humano.","","## Resumo",""]
    for name,g in groups.items(): lines.append(f"- {name}: {g['passou']}/{g['total']}")
    failures=[r for r in results if not r["passou"]]
    lines += ["", "## Falhas", ""] + ([f"- **{r['grupo']} / {r['teste']}**: {r['evidencia']}" for r in failures] or ["Nenhuma falha nos casos do benchmark."])
    out.with_suffix('.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(report['resumo'],ensure_ascii=False,indent=2))
    return 0 if not failures else 1

if __name__=='__main__': raise SystemExit(main())
