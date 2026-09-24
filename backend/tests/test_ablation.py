import json
from haila.ablation import AblationCondition,run_condition
from haila.contracts import DistratorGerado,NucleoQuestao,ReferenciaRAG

QUESTION={"enunciado":"Enunciado suficientemente detalhado para avaliar o conceito.","alternativas":["A","B","C","D","E"],"correta":0,"explicacao":"Explicação.","competencia":"C","habilidade":"H","objeto_conhecimento":"O"}
class Rag:
 def __init__(self): self.calls=0
 def __call__(self,s): self.calls+=1; return ReferenciaRAG("r1","texto","ENADE")
class Stem:
 model="stem"
 def __call__(self,s,r,f): return NucleoQuestao("Enunciado suficientemente detalhado para avaliar o conceito.","Correta","Explicação","C","H","O"),{"modelo":"stem"}
class Slm:
 model="slm"
 def __call__(self,n,f): return [DistratorGerado(x) for x in ("D1","D2","D3","D4")],{"modelo":"slm"}
def llm(s,u): return json.dumps(QUESTION)

def test_c1_nao_usa_rag_nem_slm():
 r=Rag(); out=run_condition(AblationCondition.C1_LLM,{},llm_call=llm,model='m',rag=r)
 assert r.calls==0 and out['provenance']=={'rag':False,'llm_mode':'monolithic','slm':False,'red_flags':False,'model':'m'}
def test_c2_usa_rag_e_llm_monolitica():
 r=Rag(); out=run_condition(AblationCondition.C2_RAG_LLM,{},llm_call=llm,model='m',rag=r)
 assert r.calls==1 and out['provenance']['slm'] is False
def test_c3_separa_nucleo_e_distratores_sem_red_flags():
 r=Rag(); out=run_condition(AblationCondition.C3_RAG_LLM_SLM,{},llm_call=llm,model='m',rag=r,stem_generator=Stem(),distractor_generator=Slm())
 assert [a['producer'] for a in out['artifacts']]==['RAG','LLM_STEM','SLM','ASSEMBLER'] and out['provenance']['red_flags'] is False
