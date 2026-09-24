"""Condições controladas para o estudo de ablação da HAILA."""
from __future__ import annotations
import json, time
from enum import Enum
from typing import Any, Callable

from .contracts import NucleoQuestao
from .orchestrator import montar_item


class AblationCondition(str, Enum):
    C1_LLM = "C1_LLM"
    C2_RAG_LLM = "C2_RAG_LLM"
    C3_RAG_LLM_SLM = "C3_RAG_LLM_SLM"


SYSTEM_MONOLITHIC = """Você gera uma questão objetiva inédita de Computação no formato ENADE.
Produza enunciado, exatamente cinco alternativas, índice zero-based da única correta,
explicação, competência, habilidade e objeto de conhecimento. As alternativas devem
ser paralelas, plausíveis, distintas, ter extensões semelhantes e somente uma pode
ser defensável. Use comando afirmativo; evite termos absolutos, termos vagos e pistas
lexicais ou gramaticais que destaquem o gabarito. Responda
somente JSON válido."""


def validate_question(q: dict[str, Any]) -> dict[str, Any]:
    required={"enunciado","alternativas","correta","explicacao","competencia","habilidade","objeto_conhecimento"}
    missing=required-set(q)
    if missing: raise ValueError(f"questão sem campos: {sorted(missing)}")
    if not isinstance(q["alternativas"],list) or len(q["alternativas"])!=5: raise ValueError("questão deve conter cinco alternativas")
    if type(q["correta"]) is not int or not 0<=q["correta"]<5: raise ValueError("índice de gabarito inválido")
    if len({str(x).strip().casefold() for x in q["alternativas"]})!=5: raise ValueError("alternativas duplicadas")
    q.setdefault("exame","ENADE"); q.setdefault("tem_imagem",False); q.setdefault("recurso_visual",None)
    return q


def run_condition(condition: AblationCondition, specification: dict[str,Any], *,
                  llm_call: Callable[[str,str],str], model: str,
                  rag=None, stem_generator=None, distractor_generator=None,
                  seed: str="ablation") -> dict[str,Any]:
    started=time.perf_counter(); artifacts=[]
    if condition is AblationCondition.C1_LLM:
        payload={"solicitacao":specification,"referencia":None,
                 "schema":{"enunciado":"string","alternativas":["5 strings"],"correta":"integer 0-4","explicacao":"string","competencia":"string","habilidade":"string","objeto_conhecimento":"string"}}
        q=validate_question(json.loads(llm_call(SYSTEM_MONOLITHIC,json.dumps(payload,ensure_ascii=False))))
        artifacts.append({"kind":"QUESTION","producer":"LLM_MONOLITHIC","payload":q,"provenance":{"token_usage_remote":getattr(llm_call,"last_usage",None)}})
    elif condition is AblationCondition.C2_RAG_LLM:
        if rag is None: raise ValueError("C2 exige RAG")
        ref=rag(specification); artifacts.append({"kind":"REFERENCE","producer":"RAG","payload":ref.to_dict()})
        payload={"solicitacao":specification,"referencia":ref.to_dict(),
                 "schema":{"enunciado":"string","alternativas":["5 strings"],"correta":"integer 0-4","explicacao":"string","competencia":"string","habilidade":"string","objeto_conhecimento":"string"}}
        q=validate_question(json.loads(llm_call(SYSTEM_MONOLITHIC,json.dumps(payload,ensure_ascii=False))))
        artifacts.append({"kind":"QUESTION","producer":"LLM_MONOLITHIC","payload":q,"provenance":{"token_usage_remote":getattr(llm_call,"last_usage",None)}})
    elif condition is AblationCondition.C3_RAG_LLM_SLM:
        if rag is None or stem_generator is None or distractor_generator is None: raise ValueError("C3 exige RAG, LLM de núcleo e SLM")
        ref=rag(specification); artifacts.append({"kind":"REFERENCE","producer":"RAG","payload":ref.to_dict()})
        nucleus,stem_prov=stem_generator(specification,ref,[]); artifacts.append({"kind":"STEM","producer":"LLM_STEM","payload":nucleus.to_dict(),"provenance":stem_prov})
        distractors,slm_prov=distractor_generator(nucleus,[])
        if len(distractors)>4: distractors=distractors[:4]
        if len(distractors)!=4: raise ValueError(f"C3 recebeu {len(distractors)} distratores")
        artifacts.append({"kind":"DISTRACTORS","producer":"SLM","payload":[d.to_dict() for d in distractors],"provenance":slm_prov})
        q=validate_question(montar_item(nucleus,distractors,seed))
        artifacts.append({"kind":"QUESTION","producer":"ASSEMBLER","payload":q})
    else:
        raise ValueError(f"condição não suportada: {condition}")
    return {"condition":condition.value,"state":"COMPLETED","question":q,"artifacts":artifacts,
            "provenance":{"rag":condition is not AblationCondition.C1_LLM,
                          "llm_mode":"monolithic" if condition in {AblationCondition.C1_LLM,AblationCondition.C2_RAG_LLM} else "stem_only",
                          "slm":condition is AblationCondition.C3_RAG_LLM_SLM,
                          "red_flags":False,"model":model},
            "elapsed_seconds":round(time.perf_counter()-started,3)}
