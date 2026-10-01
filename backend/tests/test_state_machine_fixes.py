"""Regressões das correções da máquina de estados (outubro/2026)."""
import pytest

from haila.contracts import ReferenciaRAG
from haila.domain import ESTADOS_TERMINAIS, Estado, TRANSICOES_PERMITIDAS
from haila.orchestrator import HailaOrchestrator
from haila.repository import HailaRepository


class _FalhaSempre:
    model = "fake"

    def __call__(self, *args):
        raise ValueError("JSON inválido")


def _orq(tmp_path):
    repo = HailaRepository(tmp_path / "t.sqlite3")
    return repo, HailaOrchestrator(repo)


def _estados(repo, rid):
    return [(e["from_state"], e["to_state"]) for e in repo.history(rid)["events"]]


def test_primeira_saida_invalida_da_llm_nao_quebra_a_maquina(tmp_path):
    repo, orq = _orq(tmp_path)
    rid = orq.solicitar("u", {"tema": "x"}, max_attempts=2)["id"]
    out = orq.executar(rid, lambda s: ReferenciaRAG("r", "texto"), _FalhaSempre(), _FalhaSempre(), None)
    assert out["state"] == Estado.ATTEMPTS_EXHAUSTED.value
    eventos = _estados(repo, rid)
    assert ("REFERENCE_RETRIEVED", "BLOCKED_BY_RED_FLAGS") in eventos
    assert ("BLOCKED_BY_RED_FLAGS", "BLOCKED_BY_RED_FLAGS") in eventos


def test_rag_sem_referencia_termina_em_generation_failed(tmp_path):
    repo, orq = _orq(tmp_path)
    rid = orq.solicitar("u", {"tema": "x"})["id"]

    def rag(_):
        raise ValueError("RAG sem referência relevante")

    with pytest.raises(ValueError):
        orq.executar(rid, rag, _FalhaSempre(), _FalhaSempre(), None)
    assert repo.get_request(rid)["state"] == Estado.GENERATION_FAILED.value


def test_autotransicao_nao_declarada_e_rejeitada(tmp_path):
    repo, orq = _orq(tmp_path)
    rid = orq.solicitar("u", {"tema": "x"})["id"]
    repo.transition(rid, None, Estado.REFERENCE_RETRIEVED, "T", "ok")
    with pytest.raises(RuntimeError):
        repo.transition(rid, None, Estado.REFERENCE_RETRIEVED, "T", "autotransição não declarada")


def test_estados_terminais():
    assert ESTADOS_TERMINAIS == {Estado.GENERATION_COMPLETED, Estado.ATTEMPTS_EXHAUSTED, Estado.GENERATION_FAILED}
    assert all(not TRANSICOES_PERMITIDAS[e] for e in ESTADOS_TERMINAIS)
