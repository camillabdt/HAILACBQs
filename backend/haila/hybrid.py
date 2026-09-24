from __future__ import annotations

import json
import os
import re
import unicodedata
from enum import Enum
from itertools import combinations
from pathlib import Path
from typing import Iterable

from .contracts import DistratorGerado, NucleoQuestao


class FamiliaQuestao(str, Enum):
    COMBINACAO_ITENS = "combinacao_itens"
    ASSERCOES = "assercoes"
    RESPOSTA_CURTA = "resposta_curta"
    RESPOSTA_TEXTUAL = "resposta_textual"


TAXONOMIAS_CURADAS = (
    ("Nenhuma", "Atomicidade", "Consistência", "Isolamento", "Durabilidade"),
    ("Atomicidade", "Consistência", "Isolamento", "Durabilidade", "Serialização"),
    ("Leitura suja", "Leitura não repetível", "Leitura fantasma", "Atualização perdida", "Escrita suja"),
    ("MVCC", "Bloqueio em duas fases (2PL)", "Controle otimista por validação", "Ordenação por carimbo de tempo", "Bloqueio pessimista"),
    ("Fila", "Pilha", "Árvore binária de busca", "Tabela hash", "Heap"),
    ("Padrão SAGA", "Protocolo Two-Phase Commit (2PC)", "Protocolo Three-Phase Commit (3PC)", "Transação distribuída XA", "Bloqueio distribuído"),
    # Famílias acrescentadas após o diagnóstico local de setembro de 2026.
    # O LoRA produzia recipientes genéricos ("arquivo", "lista", "banco de
    # dados") para paginação. Aqui cada alternativa representa uma confusão
    # real entre estruturas próximas do gerenciamento de memória.
    ("Tabela de páginas", "TLB", "Tabela de segmentos", "Lista de quadros livres", "Mapa de bits da memória física"),
    (
        "Mapear endereços virtuais para endereços físicos",
        "Mapear endereços físicos para dispositivos de E/S",
        "Registrar apenas os quadros livres da memória física",
        "Armazenar cópias das páginas removidas no espaço de troca",
        "Traduzir segmentos lógicos diretamente em blocos de disco",
    ),
    # Todos são protocolos que um estudante pode associar à comunicação em
    # rede, mas nenhum oferece o fluxo de bytes confiável e ordenado do TCP.
    ("TCP", "UDP", "SCTP", "DCCP", "QUIC"),
    ("Não funcional", "Funcional", "Regra de negócio", "Requisito de interface", "Restrição de domínio"),
    (
        "Aprendizado não supervisionado",
        "Aprendizado supervisionado",
        "Aprendizado por reforço",
        "Aprendizado semissupervisionado",
        "Aprendizado autossupervisionado",
    ),
    (
        "Entrega confiável e ordenada",
        "Entrega não confiável e sem preservação de ordem",
        "Entrega confiável sem preservação de ordem",
        "Entrega ordenada sem retransmissão de perdas",
        "Entrega com baixa latência garantida",
    ),
    (
        "TCP para a primeira e UDP para a segunda",
        "UDP para a primeira e TCP para a segunda",
        "TCP para ambas as aplicações",
        "UDP para ambas as aplicações",
        "UDP para a primeira e DCCP para a segunda",
    ),
)


def normalizar_texto(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().casefold()


def _resposta_do_prompt(prompt: str) -> str:
    achado = re.search(r"### Resposta correta:\s*\n(.*?)\n\s*\n### Saida:", prompt, re.S)
    return achado.group(1).strip() if achado else ""


class MemoriaDistratoresCurados:
    """Recupera famílias conceituais reais do mesmo corpus que ajustou o SLM."""
    model = "slm-memory-curated-v1"

    def __init__(self, dataset: str | Path | None = None):
        self.grupos = [tuple(grupo) for grupo in TAXONOMIAS_CURADAS]
        caminho = Path(dataset or os.getenv(
            "HAILA_DISTRACTOR_MEMORY_DATASET",
            "dados/qwen-enade-curado-v2/treino.jsonl",
        ))
        if caminho.is_file():
            for linha in caminho.read_text(encoding="utf-8").splitlines():
                try:
                    registro = json.loads(linha)
                    resposta = _resposta_do_prompt(str(registro.get("prompt", "")))
                    conclusao = json.loads(registro.get("completion", "{}"))
                    distratores = conclusao.get("distratores", [])
                    grupo = tuple(str(x).strip().rstrip(".") for x in [resposta, *distratores])
                except (json.JSONDecodeError, TypeError):
                    continue
                if len(grupo) == 5 and all(grupo) and len({normalizar_texto(x) for x in grupo}) == 5:
                    self.grupos.append(grupo)

    @staticmethod
    def _corresponde(resposta: str, termo: str) -> bool:
        r, t = normalizar_texto(resposta), normalizar_texto(termo)
        return r == t or r.startswith(t + " pois ") or r.startswith(t + " porque ")

    def recuperar(self, resposta: str) -> tuple[list[DistratorGerado], dict] | None:
        candidatos = []
        for indice, grupo in enumerate(self.grupos):
            posicoes = [i for i,item in enumerate(grupo) if self._corresponde(resposta, item)]
            if not posicoes:
                continue
            alvo = posicoes[0]
            outros = [item for i,item in enumerate(grupo) if i != alvo]
            # Taxonomias manuais têm prioridade; depois, exemplos mais recentes
            # e completos do corpus curado.
            candidatos.append((indice >= len(TAXONOMIAS_CURADAS), -indice, outros, grupo[alvo]))
        if not candidatos:
            return None
        _,_,outros,termo = sorted(candidatos)[0]
        distratores = [
            DistratorGerado(item, "conceito_vizinho", f"conceito da mesma família de {termo}, mas não responde ao cenário")
            for item in outros[:4]
        ]
        return distratores, {
            "modelo": self.model,
            "estrategia": "familia_conceitual_curada",
            "resposta_reconhecida": termo,
        }


def classificar_familia(resposta: str, enunciado: str = "") -> FamiliaQuestao:
    r = normalizar_texto(resposta)
    e = normalizar_texto(enunciado)
    marcadores_assercoes = ("afirmacao", "assercao", "proposicao")
    if (
        "primeira" in r
        and "segunda" in r
        and any(m in r for m in marcadores_assercoes)
    ) or (
        ("porque" in e or "assercoes" in e or "afirmacoes" in e)
        and "primeira" in r
        and "segunda" in r
    ):
        return FamiliaQuestao.ASSERCOES
    if (
        re.fullmatch(r"(?:apenas os itens? )?[ivx, e]+(?:,? apenas| estao certos?)?\.?", r)
        or "todos os itens estao certos" in r
        or re.fullmatch(r"apenas (?:um|dois|tres|quatro|cinco) (?:item|itens) (?:esta|estao) certos?\.?", r)
    ):
        return FamiliaQuestao.COMBINACAO_ITENS
    if len(r.split()) <= 4:
        return FamiliaQuestao.RESPOSTA_CURTA
    return FamiliaQuestao.RESPOSTA_TEXTUAL


def _formatar_itens(itens: Iterable[str], molde: str) -> str:
    valores = list(itens)
    corpo = valores[0] if len(valores) == 1 else ", ".join(valores[:-1]) + " e " + valores[-1]
    if normalizar_texto(molde).startswith("apenas os itens"):
        return f"Apenas os itens {corpo} estão certos."
    if normalizar_texto(molde).endswith("apenas."):
        return f"{corpo}, apenas."
    return f"{corpo}."


def gerar_combinacoes(resposta: str, enunciado: str = "") -> list[DistratorGerado]:
    corretos = tuple(dict.fromkeys(re.findall(r"\b[IVX]+\b", resposta.upper())))
    universo = tuple(dict.fromkeys(re.findall(r"\b[IVX]+\b", enunciado.upper())))
    if not universo:
        universo = ("I", "II", "III", "IV", "V")
    universo = tuple(x for x in universo if x in {"I", "II", "III", "IV", "V"})
    r = normalizar_texto(resposta)
    if "todos os itens estao certos" in r:
        corretos = universo
    contagens = {"um": 1, "dois": 2, "tres": 3, "quatro": 4, "cinco": 5}
    m_contagem = re.fullmatch(r"apenas (um|dois|tres|quatro|cinco) (?:item|itens) (?:esta|estao) certos?\.?", r)
    if m_contagem:
        correta = contagens[m_contagem.group(1)]
        candidatos = [n for n in range(0, len(universo) + 1) if n != correta]
        moldes = ["Nenhum item está certo."] + [f"Apenas {n} itens estão certos." for n in candidatos if n] + ["Todos os itens estão certos."]
        unicos = []
        for texto in moldes:
            if normalizar_texto(texto) != r and normalizar_texto(texto) not in {normalizar_texto(x) for x in unicos}:
                unicos.append(texto)
        return [DistratorGerado(x, "quantidade_itens_incorreta", "quantidade de itens corretos difere do gabarito") for x in unicos[:4]]
    if not corretos or not set(corretos) <= set(universo):
        raise ValueError("não foi possível identificar a combinação correta")
    candidatos = []
    for tamanho in range(1, len(universo) + 1):
        for combo in combinations(universo, tamanho):
            if set(combo) != set(corretos):
                candidatos.append(combo)
    candidatos.sort(key=lambda c: (len(set(c) ^ set(corretos)), abs(len(c)-len(corretos)), c))
    if len(candidatos) < 4:
        raise ValueError("universo insuficiente para quatro combinações distintas")
    return [DistratorGerado(_formatar_itens(c, resposta), "combinacao_incorreta", "combinação difere do gabarito") for c in candidatos[:4]]


def gerar_assercoes(resposta: str) -> list[DistratorGerado]:
    alternativas = [
        "a primeira afirmação é verdadeira, e a segunda é falsa.",
        "a primeira afirmação é falsa, e a segunda é verdadeira.",
        "as duas afirmações são verdadeiras, e a segunda justifica a primeira.",
        "as duas afirmações são verdadeiras, mas a segunda não justifica a primeira.",
        "as duas afirmações são falsas.",
    ]
    correta = normalizar_texto(resposta)
    def chave(texto: str):
        t = normalizar_texto(texto)
        if "duas" in t and "fals" in t: return (False, False, None)
        p = False if re.search(r"primeir[ao].{0,35}fals", t) else True
        s = False if re.search(r"segund[ao].{0,35}fals", t) else True
        justifica = None if not (p and s) else ("nao justifica" not in t and "nao e justificativa" not in t)
        return (p, s, justifica)
    chave_correta = chave(correta)
    saida = [x for x in alternativas if chave(x) != chave_correta]
    return [DistratorGerado(x, "relacao_entre_assercoes_incorreta", "relação lógica difere do gabarito") for x in saida[:4]]


class HybridDistractorGenerator:
    """Roteia formatos fechados para regras e texto livre para o SLM."""
    def __init__(self, slm, memoria=None, use_memory=None, use_rules=None):
        self.slm = slm
        self.memoria = memoria or MemoriaDistratoresCurados()
        self.use_memory = (
            os.getenv("HAILA_USE_CURATED_MEMORY", "1") == "1"
            if use_memory is None else bool(use_memory)
        )
        self.use_rules = (
            os.getenv("HAILA_USE_DETERMINISTIC_DISTRACTOR_RULES", "1") == "1"
            if use_rules is None else bool(use_rules)
        )
        modo = "hybrid-v8" if self.use_memory or self.use_rules else "slm-only-v1"
        self.model = f"{modo}({getattr(slm, 'model', 'slm')})"

    def __call__(self, nucleo: NucleoQuestao, feedback):
        familia = classificar_familia(nucleo.resposta_correta, nucleo.enunciado)
        if self.use_rules and familia == FamiliaQuestao.COMBINACAO_ITENS:
            ds = gerar_combinacoes(nucleo.resposta_correta, nucleo.enunciado)
            return ds, {"modelo": "deterministic-v8", "familia": familia.value}
        if self.use_rules and familia == FamiliaQuestao.ASSERCOES:
            ds = gerar_assercoes(nucleo.resposta_correta)
            return ds, {"modelo": "deterministic-v8", "familia": familia.value}
        # Uma família curada rejeitada pela auditoria não pode ser devolvida
        # identicamente em todas as tentativas seguintes.
        recuperado = (
            self.memoria.recuperar(nucleo.resposta_correta)
            if self.use_memory and not feedback else None
        )
        if recuperado:
            ds, prov = recuperado
            return ds, dict(prov, familia=familia.value, roteador="hybrid-v8")
        ds, prov = self.slm(nucleo, feedback)
        return ds, dict(prov, familia=familia.value, roteador="hybrid-v8")
