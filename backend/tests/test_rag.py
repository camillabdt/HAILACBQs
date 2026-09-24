import json

import pytest

from haila.rag import CorpusJsonlRAG


def test_rag_recupera_tema_relevante_e_recusa_tema_ausente(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        json.dumps({"id": "acid", "texto": "Transações de banco de dados preservam atomicidade, consistência, isolamento e durabilidade.", "exame": "ENADE", "curso": "Computação", "componente": "ESPECIFICO", "objeto_conhecimento": "Transações ACID"}) + "\n",
        encoding="utf-8",
    )
    rag = CorpusJsonlRAG(corpus)
    referencia = rag({"curso": "Computação", "componente": "ESPECIFICO", "exame": "ENADE", "objeto_conhecimento": "Transações ACID", "objetivo_pedagogico": "Diferenciar atomicidade e durabilidade em transações"})
    assert referencia.id == "acid"
    with pytest.raises(ValueError, match="sem referência relevante"):
        rag({"curso": "Computação", "componente": "ESPECIFICO", "exame": "ENADE", "objeto_conhecimento": "Compiladores", "objetivo_pedagogico": "Analisar geração de código intermediário"})
