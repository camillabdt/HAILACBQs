"""API do backend HAILA para geração e revisão de questões."""
from __future__ import annotations
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Literal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, SecretStr
from .generator import slm_generator_from_env, stem_generator_from_env
from .iwf import evaluate_iwf
from .ablation import AblationCondition,run_condition
from .generator import BestOfNDistractorGenerator,DeterministicPoolSelector,QwenDistractorGenerator
from .domain import Estado
from .rag import rag_from_env
from .orchestrator import HailaOrchestrator
from .redflags import deterministic_analyzer_from_env
from .repository import HailaRepository

app=FastAPI(title="HAILA Backend",version="1.0.0")
_DEFAULT_DB = Path(__file__).resolve().parents[2] / "runtime" / "haila.sqlite3"
repo=HailaRepository(os.getenv("HAILA_DB",str(_DEFAULT_DB))); haila=HailaOrchestrator(repo)
API_BUILD="20260924-17"

_OBJETIVO_GENERICO = {
    "analisar", "analise", "compreender", "entender", "saber", "responder",
    "conteudo", "assunto", "tema", "questao", "detalhadamente", "completa",
    "completo", "o", "a", "de", "do", "da", "e", "um", "uma",
}


def objetivo_generico(texto: str) -> bool:
    base = unicodedata.normalize("NFKD", texto.casefold())
    base = "".join(c for c in base if not unicodedata.combining(c))
    palavras = re.findall(r"[a-z]+", base)
    return not palavras or all(palavra in _OBJETIVO_GENERICO for palavra in palavras)

MODELOS_GROQ = {
    "openai/gpt-oss-120b": "Recomendado · maior modelo de produção",
    "qwen/qwen3.8-27b": "Alternativa experimental · raciocínio e JSON estrito",
    "openai/gpt-oss-20b": "Mais rápido e econômico",
}

class Solicitacao(BaseModel):
    solicitante_id:str; curso:str="Computação"; exame:Literal["ENADE"]="ENADE"
    componente:Literal["FORMACAO_GERAL","ESPECIFICO"]="ESPECIFICO"
    objetivo_pedagogico:str; dificuldade:int=Field(default=3,ge=1,le=5)
    competencia:str|None=None; habilidade:str|None=None; objeto_conhecimento:str|None=None
    restricoes:list[str]=Field(default_factory=list)
    max_tentativas:int=Field(default=3,ge=1,le=20)
    max_tentativas_distratores:int=Field(default=3,ge=1,le=20)

class ConfiguracaoGroq(BaseModel):
    api_key:SecretStr
    modelo:Literal["openai/gpt-oss-120b","qwen/qwen3.8-27b","openai/gpt-oss-20b"]="openai/gpt-oss-120b"

class AvaliacaoHumana(BaseModel):
    reviewer_role:Literal["PROFESSOR_RESPONSAVEL","PROFESSOR_CONVIDADO"]
    reviewer_name:str=Field(min_length=2,max_length=160)
    decision:Literal["APROVAR","REJEITAR"]
    audit_percentage:Literal[0,50,100]
    comments:str=Field(default="",max_length=5000)
    red_flags:list[str]=Field(default_factory=list)

class AvaliacaoAutomatica(BaseModel):
    question:dict[str,Any]
    reference:str=""

class ExecucaoAblacao(BaseModel):
    condition:Literal["C1_LLM","C2_RAG_LLM","C3_RAG_LLM_SLM"]
    specification:dict[str,Any]
    seed:str="ablation"

_ABLATION_SLM=None

def ablation_slm():
    global _ABLATION_SLM
    if _ABLATION_SLM is None:
        base=os.getenv("HAILA_SLM_BASE_MODEL","Qwen/Qwen2.5-1.5B-Instruct")
        adapter=os.getenv("HAILA_SLM_ADAPTER_PATH","").strip() or None
        _ABLATION_SLM=BestOfNDistractorGenerator(QwenDistractorGenerator(base,adapter),DeterministicPoolSelector())
    return _ABLATION_SLM

def executar(acao):
    try:return acao()
    except KeyError as exc:raise HTTPException(404,str(exc)) from exc
    except (ValueError,RuntimeError) as exc:raise HTTPException(409,str(exc)) from exc

@app.get("/health")
def health():
    backend=os.getenv("HAILA_SLM_BACKEND","qwen").strip().casefold()
    adapter=os.getenv("HAILA_SLM_ADAPTER_PATH","").strip()
    adapter_ok=bool(adapter) and Path(adapter).exists()
    slm_ok=backend=="qwen" or adapter_ok
    return {"status":"ok","service":"HAILA","build":API_BUILD,"llm_configured":bool(os.getenv("GROQ_API_KEY")),
            "slm_backend":backend,"slm_configured":slm_ok,
            # Distingue explicitamente o Qwen base do Qwen ajustado com LoRA.
            "slm_adapter_path":adapter or None,"slm_adapter_loaded":adapter_ok,
            "slm_mode":"lora" if adapter_ok else "base",
            "distractor_memory":os.getenv("HAILA_USE_CURATED_MEMORY","1") == "1",
            "distractor_rules":os.getenv("HAILA_USE_DETERMINISTIC_DISTRACTOR_RULES","1") == "1",
            "rag_corpus":os.getenv("HAILA_RAG_CORPUS",str(Path(__file__).resolve().parents[1]/"fontes_rag.jsonl")),
            "red_flags":"deterministic-v3.1","database":"configured"}

@app.get("/settings/groq")
def consultar_groq():
    return {
        "configured": bool(os.getenv("GROQ_API_KEY")),
        "modelo": os.getenv("HAILA_STEM_MODEL", "openai/gpt-oss-120b"),
        "recomendado": "openai/gpt-oss-120b",
        "modelos": [{"id": chave, "descricao": descricao} for chave,descricao in MODELOS_GROQ.items()],
        "persistencia": "memoria_da_sessao",
    }

@app.post("/settings/groq")
def configurar_groq(payload:ConfiguracaoGroq):
    chave=payload.api_key.get_secret_value().strip()
    if len(chave)<20:
        raise HTTPException(422,"Chave Groq inválida ou incompleta.")
    try:
        from openai import OpenAI
        modelos={m.id for m in OpenAI(api_key=chave,base_url="https://api.groq.com/openai/v1",timeout=20,max_retries=0).models.list().data}
    except Exception as exc:
        raise HTTPException(400,"A Groq recusou a chave ou não respondeu. Confira a chave e tente novamente.") from exc
    if payload.modelo not in modelos:
        raise HTTPException(409,f"O modelo {payload.modelo} não está disponível nesta conta Groq.")
    os.environ["GROQ_API_KEY"]=chave
    os.environ["HAILA_STEM_MODEL"]=payload.modelo
    return {"configured":True,"modelo":payload.modelo,"persistencia":"memoria_da_sessao"}

@app.post("/requests",status_code=201)
def criar_solicitacao(payload:Solicitacao):
    if objetivo_generico(payload.objetivo_pedagogico):
        raise HTTPException(422,
            "Descreva a habilidade e o conceito a avaliar. Exemplo: diferenciar leitura suja de leitura não repetível.")
    data=payload.model_dump(); ma=data.pop("max_tentativas"); md=data.pop("max_tentativas_distratores")
    return executar(lambda:haila.solicitar(payload.solicitante_id,data,ma,md))

@app.post("/requests/{request_id}/generate")
def gerar(request_id:str):
    try:
        return executar(lambda:haila.executar(request_id,rag_from_env(),stem_generator_from_env(),
                                               slm_generator_from_env(),deterministic_analyzer_from_env()))
    except HTTPException:
        raise
    except Exception as exc:
        rate_limited = getattr(exc,"status_code",None)==429 or exc.__class__.__name__=="RateLimitError"
        timed_out = exc.__class__.__name__ in {"APITimeoutError", "APIConnectionError"}
        if rate_limited or timed_out:
            status = 429 if rate_limited else 504
            code = "groq_rate_limit" if rate_limited else "groq_timeout"
            message = (
                "Limite da Groq atingido. Aguarde a renovação da cota ou escolha outro modelo."
                if rate_limited else
                "A Groq não respondeu dentro do limite de tempo. Tente novamente mais tarde."
            )
            repo.save_artifact(request_id,"provider_error",{
                "code":code,"status":status,"message":message,
            },{"provider":"groq"})
            try:
                repo.transition(request_id,None,Estado.GENERATION_FAILED,"HAILA",message,{"provider":"groq","status":status})
            except RuntimeError:
                # O artefato permanece disponível mesmo se a solicitação já
                # tiver alcançado um estado terminal concorrente.
                pass
            raise HTTPException(status,message) from exc
        raise

@app.get("/requests/{request_id}")
def consultar(request_id:str):return executar(lambda:repo.history(request_id))

@app.post("/requests/{request_id}/reviews",status_code=201)
def registrar_avaliacao(request_id:str,payload:AvaliacaoHumana):
    def salvar():
        version=repo.latest_version(request_id)
        return repo.add_review(
            request_id,version["id"],payload.reviewer_role,payload.reviewer_name,"HUMANO",
            payload.decision,payload.audit_percentage,payload.comments,payload.red_flags,
        )
    return executar(salvar)

@app.post("/evaluations/iwf")
def avaliar_iwf(payload:AvaliacaoAutomatica):
    generator=stem_generator_from_env()
    return executar(lambda:evaluate_iwf(payload.question,generator.caller,payload.reference))

@app.post("/evaluations/ablation/run")
def executar_ablacao(payload:ExecucaoAblacao):
    stem=stem_generator_from_env(); condition=AblationCondition(payload.condition)
    try:
        return executar(lambda:run_condition(
            condition,payload.specification,llm_call=stem.caller,model=stem.model,
            rag=rag_from_env() if condition is not AblationCondition.C1_LLM else None,
            stem_generator=stem if condition is AblationCondition.C3_RAG_LLM_SLM else None,
            distractor_generator=ablation_slm() if condition is AblationCondition.C3_RAG_LLM_SLM else None,
            seed=payload.seed,
        ))
    except HTTPException:
        raise
    except Exception as exc:
        status=getattr(exc,"status_code",None); name=exc.__class__.__name__
        if status==429 or name=="RateLimitError":
            raise HTTPException(429,"Limite temporário da Groq; aguarde antes de tentar novamente.") from exc
        if name in {"APITimeoutError","APIConnectionError"}:
            raise HTTPException(504,f"Falha temporária de comunicação com a Groq: {name}.") from exc
        raise HTTPException(500,f"{name}: {exc}") from exc
