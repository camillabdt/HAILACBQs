from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

from .contracts import DistratorGerado, NucleoQuestao, RedFlag
from .hybrid import FamiliaQuestao, classificar_familia


def _sim(a: str, b: str) -> float:
    norm = _normalizar
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\W+", " ", texto.casefold()).strip()



def _token_base_qualidade(token: str) -> str:
    base = unicodedata.normalize(
        "NFKD",
        str(token).casefold(),
    )
    base = "".join(
        c for c in base
        if not unicodedata.combining(c)
    )
    return re.sub(r"[^a-z0-9]", "", base)


def _tokens_qualidade(texto: str) -> list[str]:
    return re.findall(
        r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_-]*",
        str(texto),
    )


def _corrupcao_lexical(
    nucleo: NucleoQuestao,
    candidato: str,
) -> str | None:

    origem = (
        str(nucleo.enunciado)
        + " "
        + str(nucleo.resposta_correta)
    )

    bases = {}

    for token in _tokens_qualidade(origem):
        base = _token_base_qualidade(token)

        if len(base) >= 4:
            bases.setdefault(base, set()).add(
                token.casefold()
            )

    for token in _tokens_qualidade(candidato):
        base = _token_base_qualidade(token)

        if len(base) < 5:
            continue

        if base in bases:
            formas = bases[base]

            if token.casefold() not in formas:
                return (
                    f'"{token}" parece uma deformação '
                    f'ortográfica de termo presente na questão'
                )

            continue

        for original in bases:
            if len(original) < 5:
                continue

            if base[:3] != original[:3]:
                continue

            if abs(len(base) - len(original)) > 3:
                continue

            sim = SequenceMatcher(
                None,
                base,
                original,
            ).ratio()

            if sim >= 0.86:
                return (
                    f'"{token}" apresenta similaridade '
                    f'{sim:.2f} com "{original}"'
                )

    return None


def _combinacao_invalida(texto: str) -> bool:
    itens = re.findall(r"\b[IVX]+\b", texto.upper())
    return bool(itens) and len(itens) != len(set(itens))


def _resposta_formulaica(texto: str) -> bool:
    """Evita usar similaridade lexical como equivalência matemática."""
    sinais = sum(
        1 for caractere in str(texto)
        if caractere in "=<>[](){}+-×÷/¼½¾"
    )
    numeros = re.findall(r"\d+(?:[.,]\d+)?", str(texto))
    return sinais >= 2 and len(numeros) >= 2


def _opostos_conceituais_validos(a: str, b: str) -> bool:
    pares = {
        frozenset({"aprendizado supervisionado", "aprendizado nao supervisionado"}),
        frozenset({"aprendizagem supervisionada", "aprendizagem nao supervisionada"}),
        frozenset({"funcional", "nao funcional"}),
    }
    normalizados = {_normalizar(a), _normalizar(b)}
    if frozenset(normalizados) in pares:
        return True
    paradigmas = {
        "aprendizado supervisionado",
        "aprendizado nao supervisionado",
        "aprendizado semissupervisionado",
        "aprendizado autossupervisionado",
        "aprendizado por reforco",
        "aprendizagem supervisionada",
        "aprendizagem nao supervisionada",
    }
    return len(normalizados) == 2 and normalizados <= paradigmas


def avaliar_nucleo(n: NucleoQuestao, referencia: str = "") -> list[RedFlag]:
    flags = []
    add = lambda c, campo, ev: flags.append(RedFlag(c, "NUCLEO", campo, ev, "NUCLEO"))
    if len(n.enunciado.strip()) < 40: add("enunciado_ausente_ou_curto", "enunciado", f"{len(n.enunciado.strip())} caracteres")
    if not n.resposta_correta.strip(): add("resposta_correta_ausente", "resposta_correta", "campo vazio")
    if not n.explicacao.strip(): add("explicacao_ausente", "explicacao", "campo vazio")
    if not n.competencia.strip(): add("competencia_ausente", "competencia", "campo vazio")
    if not n.habilidade.strip(): add("habilidade_ausente", "habilidade", "campo vazio")
    if not n.objeto_conhecimento.strip(): add("objeto_conhecimento_ausente", "objeto_conhecimento", "campo vazio")
    resposta_norm = _normalizar(n.resposta_correta)
    enunciado_norm = _normalizar(n.enunciado)
    # O núcleo é produzido antes das alternativas. Portanto,
    # uma lista A), B), C)... dentro do enunciado é uma violação
    # arquitetural e costuma induzir a SLM a copiar/parafrasear opções.
    rotulos_embutidos = re.findall(
        r"(?<!\w)([A-E])\)\s+",
        n.enunciado,
    )

    if len(set(rotulos_embutidos)) >= 2:
        add(
            "alternativas_embutidas_no_nucleo",
            "enunciado",
            "o núcleo contém alternativas A-E; as alternativas devem ser geradas somente pela SLM",
        )

    if (
        resposta_norm
        and len(resposta_norm.split()) <= 18
        and re.search(rf"\b{re.escape(resposta_norm)}\b", enunciado_norm)
    ):
        add(
            "gabarito_repetido_no_enunciado",
            "enunciado",
            "o enunciado contém literalmente a resposta correta e pode revelar o gabarito",
        )
    # Um enunciado inteiro devolvido com barras literais ("\\n") chegava à
    # interface como uma única linha. Uma ocorrência isolada pode pertencer a
    # código-fonte (por exemplo, printf("%d\\n")); várias, sem nenhuma quebra
    # real, indicam dupla codificação do JSON.
    if n.enunciado.count("\\n") >= 2 and "\n" not in n.enunciado:
        add("formatacao_quebrada", "enunciado", "quebras de linha foram devolvidas como texto literal \\\\n")
    if n.tem_imagem and not n.recurso_visual: add("dependencia_visual_ausente", "recurso_visual", "tem_imagem=true sem recurso")
    # xmin/xmax são colunas de sistema do PostgreSQL, não um contrato genérico
    # de todo SGBD com MVCC. O piloto produziu exatamente essa generalização.
    if re.search(r"\b(?:xmin|xmax)\b", n.enunciado.casefold()) and "postgresql" not in n.enunciado.casefold():
        add("implementacao_nao_delimitada", "enunciado", "xmin/xmax exigem identificar PostgreSQL no enunciado")
    if referencia and _sim(n.enunciado, referencia) >= .82: add("possivel_copia_da_referencia", "enunciado", "similaridade lexical >= 0.82")
    pergunta_plural = bool(re.search(r"\bquais\b.{0,45}\b(?:propriedades|técnicas|mecanismos|protocolos|itens)\b", n.enunciado, re.I))
    resposta_multipla = bool(re.search(r"[,;/]|\s+e\s+", n.resposta_correta, re.I))
    if pergunta_plural and not resposta_multipla:
        add("enunciado_ambiguo", "enunciado", "pergunta plural exige mais de uma resposta, mas o gabarito é singular")
    if re.search(r"\bfuncional\s+ou\s+n[aã]o\s+funcional\b", n.enunciado, re.I):
        add(
            "espaco_de_respostas_binario",
            "enunciado",
            "o comando restringe a resposta a duas classes, mas o item objetivo exige cinco alternativas plausíveis",
        )
    if "requisito não funcional" in n.enunciado.casefold() and re.search(r"\bREQ\d+\b", n.resposta_correta, re.I):
        trechos = re.findall(r"REQ\d+\s*[–—:-]\s*(.*?)(?=;\s*REQ\d+\b|\.\s*Qual\b|$)", n.enunciado, re.I)
        marcadores = re.compile(
            r"\b(?:segundos?|milissegundos?|simult[aâ]neos?|autenticad[oa]s?|"
            r"seguran[cç]a|desempenho|disponibilidade|confiabilidade|usabilidade|"
            r"capacidade|tempo de resposta)\b",
            re.I,
        )
        candidatos = [trecho for trecho in trechos if marcadores.search(trecho)]
        if len(candidatos) > 1:
            add(
                "multiplos_candidatos_ao_gabarito",
                "enunciado",
                f"{len(candidatos)} requisitos apresentam marcadores de requisito não funcional",
            )
    if (
        _normalizar(n.resposta_correta) in {"tcp", "udp"}
        and re.search(r"\bqual\s+protocolo\b", n.enunciado, re.I)
    ):
        add(
            "selecao_de_protocolo_potencialmente_ambigua",
            "enunciado",
            "outros protocolos podem satisfazer o cenário; avalie garantias ou compare explicitamente TCP e UDP",
        )
    return flags



def _base_flexao_qualidade(token: str) -> str:
    if len(token) > 6 and token.endswith("ais"):
        return token[:-3] + "al"
    if len(token) > 6 and token.endswith("eis"):
        return token[:-3] + "el"
    if len(token) > 6 and token.endswith("ois"):
        return token[:-3] + "ol"
    if len(token) > 6 and token.endswith("oes"):
        return token[:-3] + "ao"
    if len(token) > 4 and token.endswith("s"):
        return token[:-1]
    return token


def _flexao_simples_qualidade(a: str, b: str) -> bool:
    return _base_flexao_qualidade(a) == _base_flexao_qualidade(b)


def _deformacao_lexical_do_gabarito(gabarito: str, candidato: str) -> str | None:
    origem = [_normalizar(x).replace(" ", "") for x in re.findall(
        r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_-]*", str(gabarito)
    )]
    destino = [_normalizar(x).replace(" ", "") for x in re.findall(
        r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_-]*", str(candidato)
    )]
    for token in destino:
        if len(token) < 6:
            continue
        for ref in origem:
            if len(ref) < 6 or token == ref or _flexao_simples_qualidade(token, ref):
                continue
            if token[:4] != ref[:4] or abs(len(token) - len(ref)) > 4:
                continue
            sim = SequenceMatcher(None, token, ref).ratio()
            if sim >= 0.80:
                return f'{token}~{ref}:{sim:.2f}'
    return None


def avaliar_distratores(n: NucleoQuestao, distratores: list[DistratorGerado]) -> list[RedFlag]:
    flags = []
    add = lambda c, campo, ev: flags.append(RedFlag(c, "DISTRATORES", campo, ev, "DISTRATORES"))
    familia = classificar_familia(n.resposta_correta, n.enunciado)
    formato_fechado = familia in {
        FamiliaQuestao.COMBINACAO_ITENS,
        FamiliaQuestao.ASSERCOES,
    }
    if len(distratores) != 4: add("quantidade_distratores_invalida", "distratores", f"recebidos={len(distratores)}; esperado=4")
    textos = [d.texto.strip() for d in distratores]
    rotulados = [
        (i, texto) for i, texto in enumerate(textos)
        if re.search(r"^\s*(?:\([A-E]\)|[A-E][\)\].:\-])\s*", texto, re.I)
    ]
    if rotulados:
        add(
            "distrator_com_rotulo_embutido",
            "distratores",
            "; ".join(f'{i}:{texto}' for i, texto in rotulados),
        )
    deformados = [
        (i, texto, _deformacao_lexical_do_gabarito(n.resposta_correta, texto))
        for i, texto in enumerate(textos)
    ]
    deformados = [x for x in deformados if x[2]]
    if deformados:
        add(
            "distrator_lexicalmente_corrompido",
            "distratores",
            "; ".join(f'{i}:{texto}:{motivo}' for i, texto, motivo in deformados),
        )
    if any(not t for t in textos): add("distrator_vazio", "distratores", "há texto vazio")
    norm = [_normalizar(t) for t in textos]
    if len(norm) != len(set(norm)): add("distratores_duplicados", "distratores", "há textos repetidos")
    resposta_norm = _normalizar(n.resposta_correta)
    if resposta_norm in norm:
        indice = norm.index(resposta_norm)
        add(
            "copia_normalizada_gabarito",
            f"distratores[{indice}]",
            f'"{textos[indice]}" coincide com o gabarito normalizado',
        )
    elif not formato_fechado and not _resposta_formulaica(n.resposta_correta):
        ofensores = []
        for indice, texto in enumerate(textos):
            similaridade = _sim(texto, n.resposta_correta)
            if (
                similaridade >= .82
                and not _opostos_conceituais_validos(texto, n.resposta_correta)
            ):
                ofensores.append((indice, texto, similaridade))

        if ofensores:
            evidencia = "; ".join(
                f'distratores[{indice}]="{texto}" similaridade={similaridade:.3f}'
                for indice, texto, similaridade in ofensores
            )
            add(
                "distrator_parafraseia_gabarito",
                f"distratores[{ofensores[0][0]}]",
                evidencia,
            )
    corrupcoes = []

    for indice, texto_distrator in enumerate(textos):
        motivo = _corrupcao_lexical(
            n,
            texto_distrator,
        )

        if motivo:
            corrupcoes.append(
                (indice, texto_distrator, motivo)
            )

    if corrupcoes:
        evidencia = "; ".join(
            f'distratores[{indice}]="{texto}": {motivo}'
            for indice, texto, motivo in corrupcoes
        )

        add(
            "distrator_lexicalmente_corrompido",
            "distratores",
            evidencia,
        )

    if any(_combinacao_invalida(t) for t in textos):
        add("combinacao_de_itens_invalida", "distratores", "há item romano repetido na alternativa")
    # O rótulo ``erro`` descreve uma classe de confusão, não a identidade da
    # alternativa. Quatro conceitos distintos podem legitimamente pertencer à
    # mesma classe (por exemplo, quatro técnicas vizinhas de MVCC). Bloquear
    # apenas pela repetição do rótulo causa falsos positivos e impede que a
    # memória curada seja usada. Duplicidade textual e equivalência com o
    # gabarito continuam verificadas acima; a plausibilidade é auditada depois.
    return flags


def avaliar_item(questao: dict[str, Any]) -> list[RedFlag]:
    flags = []
    add = lambda c, campo, ev: flags.append(RedFlag(c, "ITEM", campo, ev, "DISTRATORES"))
    alternativas = questao.get("alternativas") or []
    correta = questao.get("correta")
    if len(alternativas) != 5: add("quantidade_alternativas_invalida", "alternativas", f"recebidas={len(alternativas)}")
    if not isinstance(correta, int) or not 0 <= correta < len(alternativas): add("gabarito_estruturalmente_invalido", "correta", repr(correta))
    if len({str(a).strip().casefold() for a in alternativas}) != len(alternativas): add("alternativas_duplicadas", "alternativas", "há textos repetidos")
    return flags


def avaliar_estrutura_enade(questao: dict[str, Any]) -> list[dict[str, Any]]:
    """Compatibilidade temporária para registros externos do endpoint /versions."""
    try:
        correta = questao.get("correta")
        alts = questao.get("alternativas") or []
        nucleo = NucleoQuestao(questao.get("enunciado", ""), alts[correta] if isinstance(correta, int) and 0 <= correta < len(alts) else "",
                               questao.get("explicacao", ""), questao.get("competencia", "externa"),
                               questao.get("habilidade", "externa"), questao.get("objeto_conhecimento", "externo"),
                               questao.get("tem_imagem", False), questao.get("recurso_visual"))
        return [f.to_dict() for f in (avaliar_nucleo(nucleo) + avaliar_item(questao))]
    except Exception as exc:
        return [RedFlag("questao_malformada", "ITEM", "questao", str(exc), "NUCLEO").to_dict()]
