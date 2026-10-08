"""RAG local híbrido, rastreável e reproduzível da HAILA.

v4: BM25 + frases + aliases + fuzzy lexical conservador + roteamento por área
+ agregação top-k. Não inventa referência: consulta sem suporte continua bloqueada.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .contracts import ReferenciaRAG

STOPWORDS = set("""
que para uma umas uns com dos das pelo pela entre sobre como qual quais este esta esse essa
sao seu sua seus suas analisar identificar compreender computacao especifico enade objetivo
avaliar explicar comparar diferenciar descrever distinguir funcao funcoes principal conceito
conceitos funcionamento exemplo exemplos aplicacao aplicacoes uso usos sistema sistemas dados
software estudante consegue partir cenário cenario situação situacao problema correto correta
melhor seguintes considerando relação relacao acordo deve podem possui possuiem
""".split())

ALIASES = {
    "condicao_corrida": ("condicao de corrida", "condicoes de corrida", "race condition", "race conditions"),
    "exclusao_mutua": ("exclusao mutua", "mutual exclusion"),
    "regiao_critica": ("regiao critica", "critical section", "secao critica"),
    "deadlock": ("deadlock", "impasse", "interbloqueio"),
    "memoria_virtual": ("memoria virtual", "virtual memory"),
    "paginacao": ("paginacao", "paging"),
    "falta_pagina": ("falta de pagina", "faltas de pagina", "page fault", "page faults"),
    "complexidade": ("complexidade", "complexity"),
    "pilha": ("pilha", "pilhas", "stack", "stacks"),
    "fila": ("fila", "filas", "queue", "queues"),
    "transacao": ("transacao", "transacoes", "transaction", "transactions"),
    "normalizacao": ("normalizacao", "normalization"),
    "teste_unitario": ("teste unitario", "testes unitarios", "unit test", "unit tests", "unit testing"),
    "teste_integracao": ("teste de integracao", "testes de integracao", "integration testing", "integration test"),
    "aprendizado_supervisionado": ("aprendizado supervisionado", "aprendizagem supervisionada", "supervised learning"),
    "aprendizado_nao_supervisionado": ("aprendizado nao supervisionado", "aprendizagem nao supervisionada", "unsupervised learning"),
    "overfitting": ("sobreajuste", "overfitting"),
    "microsservico": ("microsservico", "microsservicos", "microservice", "microservices"),
    "autenticacao": ("autenticacao", "authentication"),
    "autorizacao": ("autorizacao", "authorization"),
    "ipv4": ("ipv4", "ip v4", "internet protocol version 4"),
    "ipv6": ("ipv6", "ip v6", "internet protocol version 6"),
    "subrede": ("subrede", "sub-redes", "sub-rede", "subnet", "subnets", "subnetting"),
    "cidr": ("cidr", "classless inter-domain routing", "prefixo de rede", "prefixo ipv4"),
    "mascara_subrede": ("mascara de subrede", "mascara de sub-rede", "subnet mask"),
    "roteamento": ("roteamento", "routing", "encaminhamento ip"),
    "roteador": ("roteador", "roteadores", "router", "routers"),
    "rota_padrao": ("rota padrao", "default route", "gateway padrao", "gateway padrão"),
    "vetor_distancia": ("vetor de distancia", "distance vector"),
    "estado_enlace": ("estado de enlace", "link state"),
    "endereco_mac": ("endereco mac", "mac address"),
    "dns": ("dns", "domain name system"),
    "http": ("http", "hypertext transfer protocol"),
    "https": ("https",),
    "tcp": ("tcp", "transmission control protocol"),
    "udp": ("udp", "user datagram protocol"),
    "banco_dados": ("banco de dados", "database", "dbms", "sgbd"),
    "engenharia_requisitos": ("engenharia de requisitos", "requirements engineering"),
    "requisito_nao_funcional": ("requisito nao funcional", "requisitos nao funcionais", "non functional requirement", "nfr"),
    "requisito_funcional": ("requisito funcional", "requisitos funcionais", "functional requirement"),
    "arvore_decisao": ("arvore de decisao", "decision tree"),
    "rede_neural": ("rede neural", "redes neurais", "neural network", "neural networks"),
    "busca_largura": ("busca em largura", "breadth first search", "bfs"),
    "busca_profundidade": ("busca em profundidade", "depth first search", "dfs"),
}

AREA_HINTS = {
    "Redes de Computadores": {"ipv4","ipv6","subrede","cidr","mascara_subrede","roteamento","roteador","rota_padrao","vetor_distancia","estado_enlace","endereco_mac","dns","http","https","tcp","udp","ethernet","icmp","dhcp","nat","bgp","ospf","rip","wifi"},
    "Banco de Dados": {"banco_dados","transacao","normalizacao","sql","acid","join","indice","serializabilidade","isolamento","relacional"},
    "Engenharia de Software": {"engenharia_requisitos","requisito_nao_funcional","requisito_funcional","scrum","uml","teste_unitario","teste_integracao","arquitetura","manutencao","rastreabilidade"},
    "Sistemas Operacionais": {"processo","thread","deadlock","memoria_virtual","paginacao","falta_pagina","escalonamento","semaforo","mutex","dma"},
    "Algoritmos e Estruturas de Dados": {"complexidade","pilha","fila","grafo","dijkstra","floyd","kruskal","prim","heap","hash","quicksort","mergesort","bfs","dfs","busca_largura","busca_profundidade"},
    "Inteligência Artificial": {"aprendizado_supervisionado","aprendizado_nao_supervisionado","overfitting","arvore_decisao","rede_neural","heuristica","minimax","kmeans","recall","precision"},
    "Segurança da Informação": {"criptografia","hash","firewall","autenticacao","autorizacao","xss","injecao","tls","pki","certificado"},
    "Arquitetura e Organização de Computadores": {"cache","pipeline","alu","registrador","multicore","complemento","datapath"},
    "Teoria da Computação": {"automato","turing","decidibilidade","np","linguagem_regular","gramatica"},
    "Compiladores e Linguagens": {"compilador","lexer","parser","ast","token","semantica","tipagem"},
    "Sistemas Distribuídos": {"distribuido","lamport","consenso","replicacao","quorum","2pc","microsservico"},
    "Interação Humano-Computador": {"usabilidade","acessibilidade","heuristica","interface","prototipo"},
    "Matemática para Computação": {"probabilidade","bayes","combinatoria","logica","relacao","grafo"},
}


def _ascii(value: Any) -> str:
    return unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()


def _canonical_text(value: Any) -> str:
    text = _ascii(value)
    pairs = [(alias, canon) for canon, aliases in ALIASES.items() for alias in aliases]
    for alias, canon in sorted(pairs, key=lambda x: -len(x[0])):
        text = re.sub(r"(?<!\w)" + re.escape(_ascii(alias)) + r"(?!\w)", canon, text)
    return re.sub(r"\s+", " ", text).strip()


def _terms(value: Any) -> list[str]:
    text = _canonical_text(value)
    raw = re.findall(r"[a-z0-9_]+", text)
    uni = [t for t in raw if (len(t) > 2 or t in {"ip","ia","p","np"}) and t not in STOPWORDS]
    # Bigrams preserve local meaning without requiring an embedding model.
    bi = [f"{a}__{b}" for a, b in zip(uni, uni[1:]) if a not in STOPWORDS and b not in STOPWORDS]
    return uni + bi


def _token_set(value: Any) -> set[str]:
    return set(_terms(value))


def _normalize_record(raw: dict[str, Any], line_no: int) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    if raw.get("quarentena") or str(raw.get("status", "")).upper() in {"REJEITADO","QUARENTENA","REJEITAR_EXTRACAO"}:
        return None
    q = raw.get("questao") if isinstance(raw.get("questao"), dict) else raw
    text = q.get("texto_base") or q.get("enunciado") or raw.get("texto")
    ident = raw.get("id") or raw.get("questao_id") or q.get("id")
    if not ident or not isinstance(text, str) or len(text.strip()) < 40:
        return None
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]", text):
        return None
    if (raw.get("tem_imagem") or q.get("tem_imagem")) and not (raw.get("recurso_visual") or q.get("recurso_visual")):
        return None
    kw = raw.get("palavras_chave") or q.get("palavras_chave") or []
    if isinstance(kw, str):
        kw = [kw]
    return {
        "id": str(ident), "texto": text.strip(),
        "ano": raw.get("ano") or q.get("ano"),
        "exame": raw.get("exame") or q.get("exame") or "ACERVO_LOCAL",
        "curso": raw.get("curso") or q.get("curso"),
        "componente": raw.get("componente") or q.get("componente"),
        "area": raw.get("area") or q.get("area"),
        "subarea": raw.get("subarea") or q.get("subarea"),
        "habilidade": raw.get("habilidade") or q.get("habilidade"),
        "objeto_conhecimento": raw.get("objeto_conhecimento") or q.get("objeto_conhecimento"),
        "palavras_chave": kw,
        "referencia": raw.get("referencia") or q.get("referencia"),
        "fonte_tipo": raw.get("fonte_tipo") or q.get("fonte_tipo"),
        "origem": raw.get("origem") or q.get("origem"),
        "linha": line_no,
    }


def _infer_area(tokens: set[str]) -> str | None:
    scores = [(len(tokens & hints), area) for area, hints in AREA_HINTS.items()]
    score, area = max(scores, default=(0, None))
    return area if score > 0 else None


def _fuzzy_hits(query_uni: set[str], doc_uni: set[str]) -> list[tuple[str,str,float]]:
    hits = []
    for q in query_uni:
        if len(q) < 5 or "__" in q or q in doc_uni:
            continue
        best = None
        for d in doc_uni:
            if len(d) < 5 or "__" in d or abs(len(q)-len(d)) > 3 or q[:2] != d[:2]:
                continue
            s = SequenceMatcher(None, q, d).ratio()
            if s >= .88 and (best is None or s > best[2]):
                best = (q, d, s)
        if best:
            hits.append(best)
    return hits


class CorpusJsonlRAG:
    """Recuperação híbrida local com agregação de evidências top-k."""

    def __init__(self, caminho: str | Path):
        self.caminho = Path(caminho)
        if not self.caminho.is_file():
            raise RuntimeError(f"corpus RAG não encontrado: {self.caminho}")
        records = []
        with self.caminho.open(encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    rec = _normalize_record(json.loads(line), n)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"JSON inválido no corpus RAG, linha {n}") from exc
                if rec:
                    records.append(rec)
        if not records:
            raise RuntimeError("corpus RAG não contém referências utilizáveis")

        unique, texts = {}, set()
        for r in records:
            normalized = re.sub(r"\s+", " ", _ascii(r["texto"])).strip()
            if r["id"] not in unique and normalized not in texts:
                unique[r["id"]] = r
                texts.add(normalized)
        self.registros = list(unique.values())

        self._doc_texts = []
        self._docs = []
        self._uni = []
        for r in self.registros:
            joined = " ".join(str(r.get(k) or "") for k in ("area","subarea","habilidade","objeto_conhecimento","palavras_chave","texto"))
            self._doc_texts.append(_canonical_text(joined))
            ts = _terms(joined)
            self._docs.append(Counter(ts))
            self._uni.append({x for x in ts if "__" not in x})

        # document frequency, not total term frequency
        self._df = Counter(t for doc in self._docs for t in doc.keys())
        self._avg_len = sum(sum(d.values()) for d in self._docs) / len(self._docs)
        self.top_k = max(1, min(5, int(os.getenv("HAILA_RAG_TOP_K", "3"))))
        self.min_score = float(os.getenv("HAILA_RAG_MIN_SCORE", "1.10"))
        self.min_focus = float(os.getenv("HAILA_RAG_MIN_FOCUS_COVERAGE", "0.30"))

    def __len__(self) -> int:
        return len(self.registros)

    def _score(self, q_terms, q_uni, focus_uni, q_area, r, doc, doc_uni, doc_text):
        common = set(q_terms) & doc.keys()
        fuzzy = _fuzzy_hits(q_uni, doc_uni)
        focus_common = focus_uni & doc_uni
        focus_cov = len(focus_common) / max(1, len(focus_uni))

        bm25 = 0.0
        dl = max(1, sum(doc.values()))
        for t in common:
            df = self._df[t]
            idf = math.log(1 + (len(self.registros) - df + .5) / (df + .5))
            tf = doc[t]
            bm25 += idf * (tf * 2.2) / (tf + 1.2 * (.25 + .75 * dl / self._avg_len))

        phrase = 0.0
        obj = _canonical_text(r.get("objeto_conhecimento"))
        for token in focus_uni:
            if token in doc_uni:
                phrase += .45
        if obj and len(obj) >= 5 and (obj in _canonical_text(" ".join(q_uni)) or any(x in doc_text for x in focus_uni)):
            phrase += .35

        area_bonus = 0.0
        r_area = _ascii(r.get("area"))
        if q_area and r_area:
            if _ascii(q_area) == r_area:
                area_bonus = 2.25
            elif q_area.casefold().split()[0] in r_area:
                area_bonus = .75

        fuzzy_bonus = sum(.35 * s for _,_,s in fuzzy[:4])
        score = bm25 + phrase + area_bonus + fuzzy_bonus
        evidence = bool(common or fuzzy)
        if focus_uni:
            evidence = evidence and (focus_cov >= self.min_focus or len(focus_common) >= 2 or area_bonus >= 2.0)
        return score, sorted(common), focus_cov, fuzzy, evidence

    def __call__(self, specification: dict[str, Any]) -> ReferenciaRAG:
        query = " ".join(str(specification.get(k) or "") for k in ("objetivo_pedagogico","competencia","habilidade","objeto_conhecimento"))
        q_terms = _terms(query)
        q_uni = {x for x in q_terms if "__" not in x}
        focus_terms = _terms(specification.get("objeto_conhecimento"))
        focus_uni = {x for x in focus_terms if "__" not in x}
        q_area = _infer_area(q_uni | focus_uni)

        ranking = []
        for r, doc, doc_uni, doc_text in zip(self.registros, self._docs, self._uni, self._doc_texts):
            if any(specification.get(k) and r.get(k) and _ascii(specification[k]) != _ascii(r[k]) for k in ("curso","componente")):
                continue
            exame = str(r.get("exame") or "")
            if specification.get("exame") and exame in {"ENADE","ENEM"} and exame != specification["exame"]:
                continue
            score, common, focus_cov, fuzzy, evidence = self._score(q_terms, q_uni, focus_uni, q_area, r, doc, doc_uni, doc_text)
            if evidence and score >= self.min_score:
                ranking.append({"score":score,"registro":r,"comuns":common,"focus":focus_cov,"fuzzy":fuzzy})

        if not ranking:
            extra = f" Área inferida: {q_area}." if q_area else ""
            raise ValueError("RAG sem referência relevante para o objetivo solicitado; amplie o acervo ou especifique o tema." + extra)

        ranking.sort(key=lambda x: (-x["score"], x["registro"]["id"]))
        best = ranking[0]["score"]

        # Top-k mantém somente fontes suficientemente próximas da principal e, quando
        # a área é inferida, evita misturar áreas sem necessidade.
        selected = []
        for item in ranking:
            if len(selected) >= self.top_k:
                break
            if item["score"] < max(self.min_score, .42 * best):
                continue
            if q_area and selected:
                area = _ascii(item["registro"].get("area"))
                if area and area != _ascii(q_area):
                    continue
            selected.append(item)
        if not selected:
            selected = [ranking[0]]

        primary = selected[0]["registro"]
        blocks = []
        sources = []
        for i, item in enumerate(selected, 1):
            r = item["registro"]
            header = f"[Fonte {i}: {r['id']} | {r.get('area') or 'sem área'} | {r.get('objeto_conhecimento') or 'sem objeto'}]"
            blocks.append(header + "\n" + r["texto"])
            sources.append({
                "id": r["id"], "area": r.get("area"), "subarea": r.get("subarea"),
                "objeto_conhecimento": r.get("objeto_conhecimento"), "referencia": r.get("referencia"),
                "score": round(item["score"], 6), "focus_coverage": round(item["focus"], 3),
                "termos_recuperados": item["comuns"],
                "fuzzy": [{"consulta":a,"documento":b,"score":round(s,3)} for a,b,s in item["fuzzy"]],
            })

        metadata = {k:v for k,v in primary.items() if k not in {"id","texto","ano","exame"}}
        metadata.update({
            "corpus": str(self.caminho),
            "retrieval": "hybrid-bm25-phrase-fuzzy-metadata-v4",
            "area_inferida": q_area,
            "top_k": len(selected),
            "fontes_ids": [x["id"] for x in sources],
            "fontes": sources,
            "candidatas_relevantes": len(ranking),
            "consulta_normalizada": sorted(q_uni),
            "ranking": [{"id":x["registro"]["id"],"score":round(x["score"],6),"area":x["registro"].get("area")} for x in ranking[:8]],
            "query_fingerprint": hashlib.sha256(query.encode()).hexdigest()[:16],
        })
        return ReferenciaRAG(id=primary["id"], texto="\n\n".join(blocks), exame=primary["exame"], ano=primary["ano"], metadados=metadata)


def rag_from_env() -> CorpusJsonlRAG:
    project_root = Path(__file__).resolve().parents[2]
    default = Path(__file__).resolve().parents[1] / "fontes_rag.jsonl"
    path = Path(os.getenv("HAILA_RAG_CORPUS", str(default))).expanduser()
    if not path.is_absolute():
        path = project_root / path
    return CorpusJsonlRAG(path.resolve())
