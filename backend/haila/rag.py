"""Recuperação local e reproduzível de referências para a HAILA."""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

from .contracts import ReferenciaRAG


STOPWORDS = set("que para uma com dos das pelo pela entre sobre como qual quais este esta esse essa sao seu sua analisar identificar compreender computacao especifico enade objetivo avaliar explicar comparar diferenciar descrever distinguir funcao principal conceito conceitos funcionamento exemplo exemplos aplicacao uso sistema sistemas dados software".split())

# Explicit equivalences, not an inferred semantic model. Same normalization for
# documents and queries; aliases never turn a related concept into a synonym.
ALIASES = {
    "condicao de corrida": ("condicoes de corrida", "race condition", "race conditions"),
    "exclusao mutua": ("mutual exclusion",),
    "regiao critica": ("critical section", "secao critica"),
    "deadlock": ("impasse", "interbloqueio"),
    "multiversao": ("mvcc", "multiversion concurrency control", "controle de concorrencia multiversao"),
    "memoria virtual": ("virtual memory",),
    "paginacao": ("paging",),
    "falta de pagina": ("page fault", "page faults", "faltas de pagina"),
    "complexidade": ("complexity",),
    "assintotica": ("asymptotic",),
    "pilhas": ("pilha", "stack", "stacks"),
    "filas": ("fila", "queue", "queues"),
    "transacoes": ("transacao", "transaction", "transactions"),
    "normalizacao": ("normalization",),
    "chaves": ("chave", "keys", "key"),
    "testes unitarios": ("teste unitario", "unit testing", "unit tests"),
    "testes de integracao": ("teste de integracao", "integration testing",),
    "aprendizado supervisionado": ("aprendizagem supervisionada", "supervised learning"),
    "aprendizado nao supervisionado": ("aprendizagem nao supervisionada", "unsupervised learning"),
    "sobreajuste": ("overfitting",),
    "microsservicos": ("microsservico", "microservices", "microservice"),
    "confidencialidade": ("confidentiality",),
    "autenticacao": ("authentication",),
    "autorizacao": ("authorization",),
}


def _normalizar_texto(valor: Any) -> str:
    return unicodedata.normalize("NFKD", str(valor or "")).encode("ascii", "ignore").decode().casefold()


def _termos(valor: Any) -> list[str]:
    texto = _normalizar_texto(valor)
    pares = [(alias, canonico) for canonico, aliases in ALIASES.items() for alias in aliases]
    for alias, canonico in sorted(pares, key=lambda x: -len(x[0])):
        texto = re.sub(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", canonico, texto)
    return [t for t in re.findall(r"[a-z0-9]+", texto)
            if (len(t) > 2 or t in {"ip", "ia"}) and t not in STOPWORDS]


def _tokens(valor: Any) -> set[str]:
    return set(_termos(valor))


def _normalizar_registro(raw: dict[str, Any], numero: int) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    if raw.get("quarentena") or str(raw.get("status", "")).upper() in {"REJEITADO", "QUARENTENA", "REJEITAR_EXTRACAO"}:
        return None
    questao = raw.get("questao") if isinstance(raw.get("questao"), dict) else raw
    texto = questao.get("texto_base") or questao.get("enunciado") or raw.get("texto")
    identificador = raw.get("id") or raw.get("questao_id") or questao.get("id")
    if not identificador or not isinstance(texto, str) or len(texto.strip()) < 40:
        return None
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]", texto):
        return None
    if (raw.get("tem_imagem") or questao.get("tem_imagem")) and not (raw.get("recurso_visual") or questao.get("recurso_visual")):
        return None
    return {
        "id": str(identificador),
        "texto": texto.strip(),
        "ano": raw.get("ano") or questao.get("ano"),
        "exame": raw.get("exame") or questao.get("exame") or "ACERVO_LOCAL",
        "curso": raw.get("curso") or questao.get("curso"),
        "componente": raw.get("componente") or questao.get("componente"),
        "area": raw.get("area") or questao.get("area"),
        "habilidade": raw.get("habilidade") or questao.get("habilidade"),
        "objeto_conhecimento": raw.get("objeto_conhecimento") or questao.get("objeto_conhecimento"),
        "referencia": raw.get("referencia") or questao.get("referencia"),
        "linha": numero,
    }


class CorpusJsonlRAG:
    """Seleciona uma referência do JSONL por metadados e similaridade lexical.

    A seleção prioriza relevância; diversidade só é aplicada entre referências
    com pontuações próximas. Consultas sem suporte são recusadas. O corpus ENADE problemático
    não é pressuposto: o caminho precisa ser informado explicitamente.
    """

    def __init__(self, caminho: str | Path):
        self.caminho = Path(caminho)
        if not self.caminho.is_file():
            raise RuntimeError(f"corpus RAG não encontrado: {self.caminho}")
        self.registros = []
        with self.caminho.open(encoding="utf-8") as arquivo:
            for numero, linha in enumerate(arquivo, 1):
                if not linha.strip():
                    continue
                try:
                    registro = _normalizar_registro(json.loads(linha), numero)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"JSON inválido no corpus RAG, linha {numero}") from exc
                if registro:
                    self.registros.append(registro)
        if not self.registros:
            raise RuntimeError("corpus RAG não contém referências utilizáveis")
        # Deduplicate before computing IDF so repeated rows cannot bias scores.
        unicos, textos = {}, set()
        for registro in self.registros:
            texto = re.sub(r"\s+", " ", _normalizar_texto(registro["texto"])).strip()
            if registro["id"] not in unicos and texto not in textos:
                unicos[registro["id"]] = registro
                textos.add(texto)
        self.registros = list(unicos.values())
        self._documentos = [Counter(_termos(" ".join(str(r.get(k) or "") for k in
                            ("area", "habilidade", "objeto_conhecimento", "texto"))))
                           for r in self.registros]
        self._frequencias = Counter(t for doc in self._documentos for t in doc)
        self._media = sum(sum(doc.values()) for doc in self._documentos) / len(self._documentos)
        self.usadas: set[str] = set()

    def __len__(self) -> int:
        return len(self.registros)

    def __call__(self, specification: dict[str, Any]) -> ReferenciaRAG:
        consulta = " ".join(str(specification.get(k) or "") for k in (
            "objetivo_pedagogico", "competencia", "habilidade", "objeto_conhecimento",
        ))
        termos = _tokens(consulta)
        foco = _tokens(specification.get("objeto_conhecimento"))
        ranking = []
        for registro, doc in zip(self.registros, self._documentos):
            if any(specification.get(k) and registro.get(k) and
                   _normalizar_texto(specification[k]) != _normalizar_texto(registro[k])
                   for k in ("curso", "componente")):
                continue
            exame = str(registro.get("exame") or "")
            if specification.get("exame") and exame in {"ENADE", "ENEM"} and exame != specification["exame"]:
                continue
            comuns = termos & doc.keys()
            foco_comum = foco & doc.keys()
            # A generic overlapping word must not silently change an explicit topic.
            if not comuns or (foco and len(foco_comum) / len(foco) < .5):
                continue
            score = 0.0
            for t in comuns:
                idf = math.log(1 + (len(self.registros) - self._frequencias[t] + .5) /
                               (self._frequencias[t] + .5))
                tf = doc[t]
                score += idf * (tf * 2.5) / (tf + 1.5 * (.25 + .75 * sum(doc.values()) / self._media))
            score += 2 * len(foco & _tokens(registro.get("objeto_conhecimento")))
            ranking.append((score, registro, sorted(comuns)))
        if not ranking:
            raise ValueError("RAG sem referência relevante para o objetivo solicitado; amplie o acervo ou especifique o tema.")
        melhor = max(x[0] for x in ranking)
        # Diversity only among close matches; never replace the topic to avoid repetition.
        elegiveis = [x for x in ranking if x[0] >= .8 * melhor]
        novas = [x for x in elegiveis if x[1]["id"] not in self.usadas]
        score, escolhido, comuns = max(novas or elegiveis, key=lambda x: (
            x[0], hashlib.sha256(f"{consulta}|{x[1]['id']}".encode()).hexdigest()))
        self.usadas.add(escolhido["id"])
        metadados = {k: v for k, v in escolhido.items() if k not in {"id", "texto", "ano", "exame"}}
        metadados.update({"corpus": str(self.caminho), "retrieval": "bm25-aliases-v3",
                         "score": round(score, 6), "termos_recuperados": comuns,
                         "candidatas_relevantes": len(ranking),
                         "consulta_normalizada": sorted(termos),
                         "ranking": [{"id": r[1]["id"], "score": round(r[0], 6)}
                                     for r in sorted(ranking, key=lambda x: (-x[0], x[1]["id"]))[:3]]})
        return ReferenciaRAG(id=escolhido["id"], texto=escolhido["texto"],
                            exame=escolhido["exame"], ano=escolhido["ano"], metadados=metadados)



def rag_from_env() -> CorpusJsonlRAG:
    padrao = Path(__file__).resolve().parents[1] / "fontes_rag.jsonl"
    caminho = os.getenv("HAILA_RAG_CORPUS", str(padrao))
    return CorpusJsonlRAG(caminho)
