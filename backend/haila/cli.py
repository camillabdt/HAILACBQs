from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .generator import slm_generator_from_env, stem_generator_from_env
from .orchestrator import HailaOrchestrator
from .rag import rag_from_env
from .redflags import deterministic_analyzer_from_env
from .repository import HailaRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="Motor HAILA para geração de questões")
    parser.add_argument("--objeto", required=True, help="objeto de conhecimento")
    parser.add_argument("--objetivo", required=True, help="objetivo pedagógico")
    parser.add_argument("--curso", default="Computação")
    parser.add_argument("--componente", default="ESPECIFICO", choices=["ESPECIFICO", "FORMACAO_GERAL"])
    parser.add_argument("--dificuldade", type=int, default=3, choices=range(1, 6))
    parser.add_argument("--solicitante", default="cli")
    parser.add_argument("--tentativas-nucleo", type=int, default=3)
    parser.add_argument("--tentativas-distratores", type=int, default=3)
    parser.add_argument("--saida", type=Path, default=Path("runtime/ultima_questao.json"))
    args = parser.parse_args()

    default_db = Path(__file__).resolve().parents[2] / "runtime" / "haila.sqlite3"
    repo = HailaRepository(os.getenv("HAILA_DB", str(default_db)))
    motor = HailaOrchestrator(repo)
    especificacao = {
        "exame": "ENADE",
        "curso": args.curso,
        "componente": args.componente,
        "objetivo_pedagogico": args.objetivo,
        "objeto_conhecimento": args.objeto,
        "dificuldade": args.dificuldade,
    }
    solicitacao = motor.solicitar(
        args.solicitante,
        especificacao,
        max_attempts=args.tentativas_nucleo,
        max_distractor_attempts=args.tentativas_distratores,
    )
    resultado = motor.executar(
        solicitacao["id"],
        rag_from_env(),
        stem_generator_from_env(),
        slm_generator_from_env(),
        deterministic_analyzer_from_env(),
    )
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    print(f"\nsalvo em: {args.saida}")
    return 0 if resultado.get("state") == "GENERATION_COMPLETED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
