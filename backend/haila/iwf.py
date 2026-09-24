"""Avaliação automática inspirada no IWF/SAQUET e em Arif et al. (2024)."""
from __future__ import annotations
import json, re, unicodedata

IWF_CRITERIA=("longest_option_correct","ambiguous_information","implausible_distractors","true_or_false",
"absolute_terms","complex_k_type","negatively_worded","convergence_cues","lost_sequence","unfocused_stem",
"none_of_the_above","word_repeats","more_than_one_correct","logical_cues","all_of_the_above",
"fill_in_the_blank","vague_terms","grammatical_cues","gratuitous_information")
SEMANTIC={"ambiguous_information","implausible_distractors","convergence_cues","unfocused_stem",
"more_than_one_correct","logical_cues","grammatical_cues","gratuitous_information"}

def norm(x):
    s=unicodedata.normalize("NFKD",str(x or "").casefold())
    return "".join(c for c in s if not unicodedata.combining(c))

def deterministic_iwf(q):
    stem=str(q.get("enunciado") or ""); opts=[str(x or "") for x in q.get("alternativas") or []]; c=q.get("correta")
    correct=opts[c] if isinstance(c,int) and 0<=c<len(opts) else ""; alltext=" ".join([stem,*opts]); n=norm(alltext)
    lengths=[len(re.findall(r"\w+",x)) for x in opts]
    out={k:None for k in IWF_CRITERIA}
    out.update({
      "longest_option_correct": bool(lengths and isinstance(c,int) and lengths[c]==max(lengths) and lengths[c]>=max(3,min(lengths or [0])+2)),
      "true_or_false": sum(bool(re.fullmatch(r"\s*(verdadeir[oa]|fals[oa]|sim|nao)\s*\.?",norm(x))) for x in opts)>=2,
      "absolute_terms": bool(re.search(r"\b(sempre|nunca|jamais|todos?|nenhum)\b",n)),
      "complex_k_type": bool(re.search(r"\b(?:I|II|III|IV|V)(?:\s*(?:,|e)\s*(?:I|II|III|IV|V))+", " ".join(opts))),
      "negatively_worded": bool(re.search(r"\b(exceto|incorreta|nao corresponde|nao e)\b",norm(stem))),
      "lost_sequence": False,
      "none_of_the_above": any(re.search(r"\bnenhuma das (?:alternativas|anteriores)\b",norm(x)) for x in opts),
      "all_of_the_above": any(re.search(r"\btodas as (?:alternativas|anteriores)\b",norm(x)) for x in opts),
      "fill_in_the_blank": bool(re.search(r"_{3,}|\.{3,}|\[\s*\]",stem)),
      "vague_terms": bool(re.search(r"\b(frequentemente|ocasionalmente|geralmente|raramente|muitas vezes)\b",n)),
    })
    sw={"qual","quais","uma","para","como","deve","pode","sistema","considerando"}
    stem_words={w for w in re.findall(r"[a-z0-9]+",norm(stem)) if len(w)>3 and w not in sw}
    repeated=stem_words & {w for w in re.findall(r"[a-z0-9]+",norm(correct)) if len(w)>3}
    other=" ".join(x for i,x in enumerate(opts) if i!=c)
    out["word_repeats"]=bool(repeated and not any(w in norm(other) for w in repeated))
    return out

def semantic_prompt(q,reference=""):
    return """Avalie uma questão de múltipla escolha. Não reescreva. Para cada critério, flaw=true somente quando houver evidência concreta. Verifique especialmente se há mais de uma alternativa defensável e se cada distrator é plausível mas incorreto. Responda apenas JSON no schema solicitado. A avaliação é automática e conservadora.""", json.dumps({
      "questao":q,"referencia":reference,"criterios_semanticos":sorted(SEMANTIC),
      "metricas_arif":["relevance","grammar","answerability","clarity","contextual_specificity","question_option_disjoint","distractor_homogeneity","distractor_plausibility"],
      "schema":{"iwf":{k:{"flaw":"boolean","evidence":"string"} for k in sorted(SEMANTIC)},
                "arif":{k:{"pass":"boolean","evidence":"string"} for k in ["relevance","grammar","answerability","clarity","contextual_specificity","question_option_disjoint","distractor_homogeneity","distractor_plausibility"]}}
    },ensure_ascii=False)

def _named_objects(value, name_keys):
    """Aceita mapa canônico e listas nomeadas devolvidas por alguns modelos."""
    if isinstance(value,dict): return value
    out={}
    if not isinstance(value,list): return out
    for item in value:
        if not isinstance(item,dict): continue
        name=next((item.get(k) for k in name_keys if item.get(k)),None)
        if name:
            payload={k:v for k,v in item.items() if k not in name_keys}
            out[str(name)]=payload
        elif len(item)==1:
            key,payload=next(iter(item.items()))
            out[str(key)]=payload if isinstance(payload,dict) else {}
    return out

def evaluate_iwf(q,caller=None,reference=""):
    values=deterministic_iwf(q); evidence={k:"regra determinística" for k,v in values.items() if v is not None}
    arif={}
    if caller:
        system,user=semantic_prompt(q,reference); data=json.loads(caller(system,user))
        if not isinstance(data,dict): data={}
        iwf_data=_named_objects(data.get("iwf"), ("criterion","criterio","name","nome"))
        for k,v in iwf_data.items():
            if k in SEMANTIC and isinstance(v,dict): values[k]=bool(v.get("flaw")); evidence[k]=str(v.get("evidence") or "")
        arif=_named_objects(data.get("arif"), ("metric","metrica","name","nome"))
    unresolved=[k for k,v in values.items() if v is None]
    flaws=[k for k,v in values.items() if v is True]
    result={"iwf":values,"evidence":evidence,"flaws":flaws,"iwf_count":len(flaws),
            "classification":"acceptable" if not unresolved and len(flaws)<=1 else ("unacceptable" if not unresolved else "incomplete"),
            "unresolved":unresolved,"arif":arif}
    usage=getattr(caller,"last_usage",None) if caller else None
    if usage: result["evaluator_token_usage_remote"]=dict(usage)
    return result
