from __future__ import annotations

from haila.contracts import DistratorGerado, NucleoQuestao, RedFlag, ReferenciaRAG
from haila.orchestrator import HailaOrchestrator
from haila.repository import HailaRepository
from haila.hybrid import MemoriaDistratoresCurados


class _Rag:
    def __init__(self):
        self.calls = 0

    def __call__(self, _spec):
        self.calls += 1
        return ReferenciaRAG(
            id="ref-1",
            texto="Referência conceitual sobre estruturas de dados e política FIFO.",
        )


class _Stem:
    model = "fake-llm"

    def __init__(self):
        self.calls = 0

    def __call__(self, _spec, _ref, _feedback):
        self.calls += 1
        return (
            NucleoQuestao(
                enunciado=(
                    "Uma aplicação precisa processar solicitações exatamente na ordem "
                    "em que elas chegam. Qual estrutura de dados atende diretamente a "
                    "esse comportamento?"
                ),
                resposta_correta="Fila",
                explicacao="Uma fila segue FIFO e preserva a ordem de chegada.",
                competencia="Analisar estruturas de dados",
                habilidade="Selecionar a estrutura adequada",
                objeto_conhecimento="Filas e pilhas",
            ),
            {"modelo": self.model},
        )


class _IncrementalDistractors:
    model = "fake-slm"

    def __init__(self):
        self.calls = 0

    def generate_candidates(
        self,
        _nucleo,
        _feedback,
        target_count=4,
        avoid_texts=None,
        max_samples=1,
    ):
        self.calls += 1
        if self.calls == 1:
            return (
                [
                    DistratorGerado("Pilha"),
                    DistratorGerado("Fila"),  # must be rejected: copy of answer
                    DistratorGerado("Árvore binária de busca"),
                ],
                {"modelo": self.model, "target_count": target_count},
            )
        return (
            [DistratorGerado("Tabela hash"), DistratorGerado("Heap")],
            {"modelo": self.model, "target_count": target_count},
        )

    def select_from_pool(self, _nucleo, pool):
        return pool[:4], {
            "modelo": "fake-selector",
            "indices_selecionados": [0, 1, 2, 3],
        }


class _AdvisoryAnalyzer:
    def __call__(self, _question, _spec, _reference):
        return (
            [
                RedFlag(
                    "iwf_termo_absoluto",
                    "DETERMINISTICA",
                    "questao",
                    "alerta pedagógico de teste",
                    "NUCLEO",
                )
            ],
            {"modelo": "fake-redflag"},
        )


def test_sustainable_pipeline_keeps_good_candidates_and_calls_llm_once(tmp_path, monkeypatch):
    monkeypatch.setenv("HAILA_SUSTAINABLE_PIPELINE", "1")
    repo = HailaRepository(tmp_path / "haila.sqlite3")
    haila = HailaOrchestrator(repo)
    request = haila.solicitar(
        "teste",
        {"objetivo_pedagogico": "Selecionar a estrutura adequada"},
        3,
        3,
    )
    rag = _Rag()
    stem = _Stem()
    distractors = _IncrementalDistractors()

    result = haila.executar(
        request["id"],
        rag,
        stem,
        distractors,
        _AdvisoryAnalyzer(),
        None,
    )

    assert result["state"] == "GENERATION_COMPLETED"
    assert stem.calls == 1
    assert distractors.calls == 2

    history = repo.history(request["id"])
    accepted = [
        a for a in history["artifacts"]
        if a["kind"] == "DISTRACTOR_CANDIDATE_ACCEPTED"
    ]
    rejected = [
        a for a in history["artifacts"]
        if a["kind"] == "DISTRACTOR_CANDIDATE_REJECTED"
    ]
    checkpoints = [
        a for a in history["artifacts"]
        if a["kind"] == "DISTRACTOR_POOL_CHECKPOINT"
    ]

    assert len(accepted) >= 4
    assert any(a["payload"]["texto"] == "Fila" for a in rejected)
    assert len(checkpoints) >= 4
    assert history["latest_version"] is not None
    assert len(history["latest_version"]["question"]["alternativas"]) == 5
    assert any(f["code"] == "iwf_termo_absoluto" for f in history["red_flags"])


class _RateLimitError(Exception):
    status_code = 429


class _RateLimitedStem:
    model = "fake-llm"

    def __call__(self, *_args, **_kwargs):
        raise _RateLimitError("429")


def test_transient_provider_error_preserves_reference_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("HAILA_SUSTAINABLE_PIPELINE", "1")
    repo = HailaRepository(tmp_path / "haila.sqlite3")
    haila = HailaOrchestrator(repo)
    request = haila.solicitar(
        "teste",
        {"objetivo_pedagogico": "Selecionar a estrutura adequada"},
        3,
        3,
    )
    rag = _Rag()

    try:
        haila.executar(
            request["id"],
            rag,
            _RateLimitedStem(),
            _IncrementalDistractors(),
            _AdvisoryAnalyzer(),
            None,
        )
    except _RateLimitError:
        pass
    else:
        raise AssertionError("esperava erro transitório simulado")

    persisted = repo.get_request(request["id"])
    assert persisted["state"] == "REFERENCE_RETRIEVED"
    assert repo.latest_artifact(request["id"], "REFERENCE") is not None
    assert repo.latest_artifact(request["id"], "STEM_CHECKPOINT") is None


class _DbStem:
    model = "fake-llm"

    def __init__(self):
        self.calls = 0

    def __call__(self, _spec, _ref, _feedback):
        self.calls += 1
        return (
            NucleoQuestao(
                enunciado=(
                    "Tabela Cliente(id_cliente, nome) e Pedido(id_pedido, id_cliente). "
                    "Todo id_cliente em Pedido deve existir em Cliente. Qual é a "
                    "classificação de id_cliente em Pedido?"
                ),
                resposta_correta="chave estrangeira",
                explicacao=(
                    "O atributo referencia a chave de Cliente e implementa a "
                    "integridade referencial."
                ),
                competencia="Analisar modelos relacionais",
                habilidade="Classificar restrições e chaves",
                objeto_conhecimento="Banco de dados relacionais",
            ),
            {"modelo": self.model},
        )


class _SemanticDistractors:
    model = "fake-local-slm"

    def __init__(self):
        self.calls = 0
        self.gate_calls = 0

    def generate_candidates(
        self,
        _nucleo,
        _feedback,
        target_count=4,
        avoid_texts=None,
        max_samples=1,
    ):
        self.calls += 1
        if self.calls == 1:
            return (
                [
                    DistratorGerado("atributo primário"),
                    DistratorGerado("chave candidata"),
                    DistratorGerado("índice secundário"),
                    DistratorGerado("restrição CHECK"),
                ],
                {"modelo": self.model, "target_count": target_count},
            )
        return (
            [DistratorGerado("chave composta")],
            {"modelo": self.model, "target_count": target_count},
        )

    def validate_candidates_semantically(self, _nucleo, candidates):
        self.gate_calls += 1
        if self.gate_calls == 1:
            idx = next(i for i, c in enumerate(candidates) if c.texto == "atributo primário")
            return ([{
                "indice": idx,
                "codigo": "segunda_resposta",
                "motivo": "termo não padronizado pode ser interpretado como papel de chave",
                "texto": "atributo primário",
            }], {"enabled": True, "parse_ok": True, "modelo": self.model})
        return ([], {"enabled": True, "parse_ok": True, "modelo": self.model})

    def select_from_pool(self, _nucleo, pool):
        return pool[:4], {
            "modelo": "fake-selector",
            "indices_selecionados": [0, 1, 2, 3],
        }


def test_semantic_gate_replaces_only_ambiguous_distractor(tmp_path, monkeypatch):
    monkeypatch.setenv("HAILA_SUSTAINABLE_PIPELINE", "1")
    monkeypatch.setenv("HAILA_LOCAL_SEMANTIC_GATE", "1")
    monkeypatch.setenv("HAILA_LOCAL_SEMANTIC_GATE_MAX_PASSES", "2")
    repo = HailaRepository(tmp_path / "haila.sqlite3")
    haila = HailaOrchestrator(repo)
    request = haila.solicitar(
        "teste-semantico",
        {"objetivo_pedagogico": "Classificar chave estrangeira"},
        3,
        3,
    )
    stem = _DbStem()
    distractors = _SemanticDistractors()
    result = haila.executar(
        request["id"],
        _Rag(),
        stem,
        distractors,
        _AdvisoryAnalyzer(),
        None,
    )

    assert result["state"] == "GENERATION_COMPLETED"
    assert stem.calls == 1
    assert distractors.calls == 2
    assert distractors.gate_calls == 2

    history = repo.history(request["id"])
    final_alts = history["latest_version"]["question"]["alternativas"]
    assert "atributo primário" not in final_alts
    assert "chave composta" in final_alts

    semantic_rejections = [
        a for a in history["artifacts"]
        if a["kind"] == "DISTRACTOR_CANDIDATE_REJECTED_SEMANTIC"
    ]
    quality_rejections = [
        a for a in history["artifacts"]
        if a["kind"] == "DISTRACTOR_CANDIDATE_REJECTED_QUALITY"
    ]
    assert len(semantic_rejections) == 1
    assert len(quality_rejections) == 1
    assert semantic_rejections[0]["payload"]["texto"] == "atributo primário"

    checkpoints = [
        a for a in history["artifacts"]
        if a["kind"] == "DISTRACTOR_POOL_CHECKPOINT"
    ]
    assert any(len(a["payload"]) == 3 for a in checkpoints)
    assert len(checkpoints[-1]["payload"]) == 4


class _QualityDistractors:
    model = "fake-local-quality-slm"

    def __init__(self):
        self.calls = 0
        self.gate_calls = 0

    def generate_candidates(
        self,
        _nucleo,
        _feedback,
        target_count=4,
        avoid_texts=None,
        max_samples=1,
    ):
        self.calls += 1
        if self.calls == 1:
            return (
                [
                    DistratorGerado("Chave dupla"),
                    DistratorGerado("Chave primária"),
                    DistratorGerado("Classe cardinalária"),
                    DistratorGerado("Chaves duplicatas"),
                ],
                {"modelo": self.model, "target_count": target_count},
            )
        return (
            [
                DistratorGerado("Chave candidata"),
                DistratorGerado("Chave composta"),
                DistratorGerado("Superchave"),
            ],
            {"modelo": self.model, "target_count": target_count},
        )

    def validate_candidates_quality(self, _nucleo, candidates):
        self.gate_calls += 1
        rejeicoes = []
        for i, c in enumerate(candidates):
            if c.texto == "Chave dupla":
                rejeicoes.append({
                    "indice": i,
                    "codigo": "termo_nao_padronizado",
                    "motivo": "rótulo não padronizado para tipos de chave",
                })
            elif c.texto == "Classe cardinalária":
                rejeicoes.append({
                    "indice": i,
                    "codigo": "fora_do_dominio",
                    "motivo": "não é uma classificação de chave relacional",
                })
            elif c.texto == "Chaves duplicatas":
                rejeicoes.append({
                    "indice": i,
                    "codigo": "implausivel",
                    "motivo": "não é um tipo técnico padronizado de chave",
                })
        return rejeicoes, {
            "enabled": True,
            "parse_ok": True,
            "modelo": self.model,
            "criterios": [
                "terminologia_padronizada",
                "mesmo_dominio",
                "plausibilidade",
                "incorrecao_contextual",
                "unicidade_do_gabarito",
            ],
        }

    def select_from_pool(self, _nucleo, pool):
        return pool[:4], {"modelo": "fake-selector", "indices_selecionados": [0,1,2,3]}


def test_quality_gate_rejects_nonstandard_and_implausible_terms(tmp_path, monkeypatch):
    monkeypatch.setenv("HAILA_SUSTAINABLE_PIPELINE", "1")
    monkeypatch.setenv("HAILA_DISTRACTOR_QUALITY_GATE", "1")
    monkeypatch.setenv("HAILA_DISTRACTOR_QUALITY_MAX_REPAIRS", "3")
    repo = HailaRepository(tmp_path / "haila.sqlite3")
    haila = HailaOrchestrator(repo)
    request = haila.solicitar(
        "teste-qualidade",
        {"objetivo_pedagogico": "Classificar chave estrangeira"},
        3,
        3,
    )
    distractors = _QualityDistractors()
    result = haila.executar(
        request["id"],
        _Rag(),
        _DbStem(),
        distractors,
        _AdvisoryAnalyzer(),
        None,
    )

    assert result["state"] == "GENERATION_COMPLETED"
    history = repo.history(request["id"])
    final_alts = history["latest_version"]["question"]["alternativas"]
    assert "Chave dupla" not in final_alts
    assert "Classe cardinalária" not in final_alts
    assert "Chaves duplicatas" not in final_alts
    assert "Chave candidata" in final_alts
    assert "Chave composta" in final_alts
    assert "Superchave" in final_alts

    rejected = [
        a for a in history["artifacts"]
        if a["kind"] == "DISTRACTOR_CANDIDATE_REJECTED_QUALITY"
    ]
    codes = {a["provenance"]["quality_code"] for a in rejected}
    assert {"termo_nao_padronizado", "fora_do_dominio", "implausivel"} <= codes
    assert result["distractor_quality_gate"]["verified"] is True


class _ReserveDistractors:
    model = "fake-reserve-slm"

    def __init__(self):
        self.calls = 0
        self.gate_calls = 0

    def generate_candidates(self, _nucleo, _feedback, target_count=4, avoid_texts=None, max_samples=1):
        self.calls += 1
        return ([
            DistratorGerado("Chave primária"),
            DistratorGerado("Atributo primário"),
            DistratorGerado("Chave candidata"),
            DistratorGerado("Chave composta"),
            DistratorGerado("Superchave"),
            DistratorGerado("Restrição UNIQUE"),
        ], {"modelo": self.model, "target_count": target_count})

    def validate_candidates_quality(self, _nucleo, candidates):
        self.gate_calls += 1
        if self.gate_calls == 1:
            idx = next(i for i, c in enumerate(candidates) if c.texto == "Atributo primário")
            return ([{
                "indice": idx,
                "codigo": "termo_nao_padronizado",
                "motivo": "pode ser interpretado de forma ambígua",
            }], {"enabled": True, "parse_ok": True, "modelo": self.model})
        return ([], {"enabled": True, "parse_ok": True, "modelo": self.model})


def test_quality_gate_promotes_reserve_before_new_slm_call(tmp_path, monkeypatch):
    monkeypatch.setenv("HAILA_SUSTAINABLE_PIPELINE", "1")
    monkeypatch.setenv("HAILA_DISTRACTOR_QUALITY_GATE", "1")
    monkeypatch.setenv("HAILA_DISTRACTOR_BANK_MAX", "6")
    monkeypatch.setenv("HAILA_DISTRACTOR_QUALITY_MAX_REPAIRS", "3")
    repo = HailaRepository(tmp_path / "haila.sqlite3")
    haila = HailaOrchestrator(repo)
    request = haila.solicitar(
        "teste-reserva",
        {"objetivo_pedagogico": "Classificar chave estrangeira"},
        3,
        3,
    )
    distractors = _ReserveDistractors()
    result = haila.executar(
        request["id"],
        _Rag(),
        _DbStem(),
        distractors,
        _AdvisoryAnalyzer(),
        None,
    )

    assert result["state"] == "GENERATION_COMPLETED"
    assert distractors.calls == 1, "reserva deve evitar nova chamada ao SLM"
    assert distractors.gate_calls == 2
    assert result["distractor_quality_gate"]["verified"] is True

    history = repo.history(request["id"])
    final_alts = history["latest_version"]["question"]["alternativas"]
    assert "Atributo primário" not in final_alts
    assert "Superchave" in final_alts
    reserves = [a for a in history["artifacts"] if a["kind"] == "DISTRACTOR_CANDIDATE_RESERVE"]
    assert len(reserves) == 2
    quality_ok = [a for a in history["artifacts"] if a["kind"] == "DISTRACTOR_CANDIDATE_VALIDATED_QUALITY"]
    assert len(quality_ok) == 4


def test_curated_database_key_family_uses_real_sibling_concepts():
    memoria = MemoriaDistratoresCurados(dataset="/arquivo/que/nao/existe.jsonl")
    result = memoria.recuperar("Chave estrangeira")
    assert result is not None
    distratores, provenance = result
    textos = {d.texto for d in distratores}
    assert textos == {"Chave primária", "Chave candidata", "Chave composta", "Superchave"}
    assert provenance["estrategia"] == "familia_conceitual_curada"
