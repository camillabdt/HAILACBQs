import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("preparar_dados", RAIZ / "research/lora/preparar_dados.py")
pd = importlib.util.module_from_spec(spec); spec.loader.exec_module(pd)

BASE = {"id": "x", "enunciado": "Duas transações atualizam o mesmo saldo e uma atualização se perde. Qual anomalia ocorreu?",
        "alternativas": ["Leitura suja", "Atualização perdida", "Leitura fantasma", "Leitura não repetível", "Escrita suja"],
        "correta": 1}


def test_questao_valida_vira_exemplo_no_formato_da_inferencia():
    ex, motivo = pd.avaliar(BASE, 1.5)
    assert motivo is None
    assert "### Resposta correta:\nAtualização perdida" in ex["prompt"]
    assert "Atualização perdida" not in ex["completion"]
    assert ex["system"] == pd.SYSTEM_DISTRACTORES_QWEN


def test_filtros():
    assert pd.avaliar(dict(BASE, enunciado="Observe a figura e responda."), 1.5)[1] == "depende_de_recurso_visual"
    assert pd.avaliar(dict(BASE, alternativas=BASE["alternativas"][:4]), 1.5)[1] == "nao_tem_5_alternativas"
    longa = list(BASE["alternativas"]); longa[1] = "Atualização perdida causada pela ausência de bloqueio entre as duas escritas"
    assert pd.avaliar(dict(BASE, alternativas=longa), 1.5)[1] == "gabarito_destoa_em_extensao"


def test_particao_deterministica():
    assert pd.particao("abc", 0.15) == pd.particao("abc", 0.15)
