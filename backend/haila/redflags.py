"""Verificações determinísticas aplicadas ao item montado pela HAILA."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from .contracts import RedFlag


def _normalizar(texto: Any) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().casefold()


class DeterministicRedFlagAnalyzer:
    """Detecta problemas observáveis sem chamar outro modelo generativo."""

    model = "haila-deterministic-redflags-v3"
    catalog_version = "haila-redflags-3.0.0"

    def __call__(self, questao, specification, referencia):
        flags: list[RedFlag] = []

        def add(codigo: str, campo: str, evidencia: str, reparo: str = "NUCLEO") -> None:
            flags.append(RedFlag(codigo, "DETERMINISTICA", campo, evidencia, reparo))

        enunciado = str(questao.get("enunciado") or "")
        alternativas = [str(x or "") for x in questao.get("alternativas") or []]
        todos = " ".join([enunciado, *alternativas])
        normalizado = _normalizar(todos)

        if any(ord(c) < 32 and c not in "\n\t\r" for c in todos):
            add("formatacao_quebrada", "questao", "há caracteres de controle")
        placeholders = re.findall(r"<\s*[A-Z][A-Z0-9_-]*\s*>", todos)
        if placeholders:
            add("placeholder_residual", "questao", f"marcadores encontrados: {', '.join(sorted(set(placeholders)))}", "DISTRATORES")
        if len(enunciado) > 5000 or any(len(a) > 1200 for a in alternativas):
            add("formatacao_quebrada", "questao", "enunciado ou alternativa excede o limite seguro")
        marcadores_vazamento = (
            "questionario de percepcao",
            "rascunho",
            "area livre",
            "cartao-resposta",
            "exame nacional de desempenho dos estudantes",
        )
        achados = [marcador for marcador in marcadores_vazamento if marcador in normalizado]
        if achados:
            add("vazamento_de_artefato", "questao", f"marcadores encontrados: {', '.join(achados)}")
        if re.search(r"\bquest\s*[aã]\s*o\s+\d{1,3}\b", _normalizar(" ".join(alternativas))):
            add("vazamento_de_artefato", "alternativas", "outra questão foi anexada a uma alternativa", "DISTRATORES")
        if questao.get("tem_imagem") and not questao.get("recurso_visual"):
            add("dependencia_visual_ausente", "recurso_visual", "item exige imagem sem recurso")
        if any(not alternativa.strip() for alternativa in alternativas):
            add("formatacao_quebrada", "alternativas", "há alternativa vazia", "DISTRATORES")

        correta = questao.get("correta")
        if isinstance(correta, int) and 0 <= correta < len(alternativas):
            resposta = alternativas[correta]
            tamanhos = [len(re.findall(r"\w+", alternativa)) for alternativa in alternativas]
            if tamanhos and tamanhos[correta] == max(tamanhos) and tamanhos[correta] >= min(tamanhos) + 2:
                add(
                    "iwf_gabarito_mais_longo",
                    "alternativas",
                    f"palavras por alternativa={tamanhos}; o gabarito não deve se destacar pela extensão",
                    "DISTRATORES",
                )

            stop = {"qual", "quais", "uma", "para", "como", "deve", "pode", "sistema", "considerando"}
            palavras_enunciado = {
                p for p in re.findall(r"[a-z0-9]+", _normalizar(enunciado))
                if len(p) > 3 and p not in stop
            }
            palavras_resposta = {
                p for p in re.findall(r"[a-z0-9]+", _normalizar(resposta))
                if len(p) > 3
            }
            repetidas = palavras_enunciado & palavras_resposta
            outros = _normalizar(" ".join(a for i, a in enumerate(alternativas) if i != correta))
            pistas = sorted(p for p in repetidas if p not in outros)
            if pistas:
                add(
                    "iwf_repeticao_entrega_gabarito",
                    "enunciado",
                    f"termos exclusivos repetidos no gabarito: {', '.join(pistas)}",
                    "NUCLEO",
                )

        if re.search(r"\b(exceto|incorreta|nao corresponde|nao e)\b", _normalizar(enunciado)):
            add("iwf_comando_negativo", "enunciado", "reformule o comando de maneira afirmativa", "NUCLEO")

        absolutos = re.findall(r"\b(sempre|nunca|jamais|todos?|nenhum)\b", normalizado)
        if absolutos:
            add(
                "iwf_termo_absoluto",
                "questao",
                f"termos absolutos encontrados: {', '.join(sorted(set(absolutos)))}",
                "NUCLEO",
            )

        vagos = re.findall(r"\b(frequentemente|ocasionalmente|geralmente|raramente|muitas vezes)\b", normalizado)
        if vagos:
            add(
                "iwf_termo_vago",
                "questao",
                f"termos vagos encontrados: {', '.join(sorted(set(vagos)))}",
                "NUCLEO",
            )

        return flags, {
            "modelo": self.model,
            "catalog_version": "haila-redflags-3.1.0",
            "tipo": "deterministico",
        }


def deterministic_analyzer_from_env() -> DeterministicRedFlagAnalyzer:
    return DeterministicRedFlagAnalyzer()
