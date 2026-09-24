import json
from haila.iwf import evaluate_iwf, SEMANTIC


QUESTION={"enunciado":"Qual conceito se aplica ao cenário descrito?","alternativas":["A","B","C","D","E"],"correta":0}


def test_aceita_iwf_em_lista_nomeada():
    def caller(system,user):
        return json.dumps({
            "iwf":[{"criterion":k,"flaw":False,"evidence":"ausente"} for k in sorted(SEMANTIC)],
            "arif":[{"metric":"clarity","pass":True,"evidence":"clara"}],
        })
    result=evaluate_iwf(QUESTION,caller)
    assert result["unresolved"]==[]
    assert result["classification"]=="acceptable"
    assert result["arif"]["clarity"]["pass"] is True
