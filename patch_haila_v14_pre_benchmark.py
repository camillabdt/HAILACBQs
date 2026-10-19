#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path.home() / "HAILA"
HYBRID = ROOT / "backend/haila/hybrid.py"
STRUCTURAL = ROOT / "backend/haila/structural.py"
GENERATOR = ROOT / "backend/haila/generator.py"
SMOKE = ROOT / "testar_haila_3_questoes.py"
TEST = ROOT / "backend/tests/test_v14_pre_benchmark.py"
FILES = (HYBRID, STRUCTURAL, GENERATOR, SMOKE)
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
BACKUP = ROOT.parent / f"HAILA-backup-v14-{STAMP}"


def fail(msg: str):
    raise RuntimeError(msg)


if not ROOT.is_dir():
    print("❌ Não encontrei", ROOT)
    sys.exit(1)
for path in FILES:
    if not path.is_file():
        print("❌ Arquivo ausente:", path)
        sys.exit(1)

BACKUP.mkdir(parents=True, exist_ok=True)
for path in FILES:
    dst = BACKUP / path.relative_to(ROOT)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)

print("=" * 78)
print("HAILA v14 — pré-benchmark")
print("=" * 78)
print("Backup:", BACKUP)

try:
    # 1) Memória curada de requisitos.
    txt = HYBRID.read_text(encoding="utf-8")
    grupo = (
        '    ("Requisito funcional", "Requisito não funcional", '
        '"Regra de negócio", "Restrição de projeto", "Critério de aceitação"),\n'
    )
    assinatura = '"Requisito funcional", "Requisito não funcional", "Regra de negócio"'
    if assinatura not in txt:
        marker = "TAXONOMIAS_CURADAS = (\n"
        if marker not in txt:
            fail("TAXONOMIAS_CURADAS não encontrada em hybrid.py")
        txt = txt.replace(marker, marker + grupo, 1)
        print("✅ Família curada geral de requisitos adicionada")
    else:
        print("ℹ️ Família curada geral de requisitos já existe")
    HYBRID.write_text(txt, encoding="utf-8")

    # 2) Opostos conceituais completos.
    txt = STRUCTURAL.read_text(encoding="utf-8")
    pair_anchor = '        frozenset({"funcional", "nao funcional"}),\n'
    pair_full = '        frozenset({"requisito funcional", "requisito nao funcional"}),\n'
    pair_plural = '        frozenset({"requisitos funcionais", "requisitos nao funcionais"}),\n'
    if pair_full not in txt:
        if pair_anchor not in txt:
            fail("par funcional/não funcional não encontrado em structural.py")
        txt = txt.replace(pair_anchor, pair_anchor + pair_full + pair_plural, 1)
        print("✅ Requisito funcional × não funcional reconhecidos como opostos")
    else:
        print("ℹ️ Opostos completos já configurados")

    # 3) Flexões contextuais válidas.
    if "def _flexao_contextual_valida(" not in txt:
        marker = "\ndef _corrupcao_lexical("
        if marker not in txt:
            fail("_corrupcao_lexical não encontrada")
        helper = r'''

def _base_flexao_contextual(token: str) -> str:
    token = _token_base_qualidade(token)
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


def _flexao_contextual_valida(a: str, b: str) -> bool:
    aa = _base_flexao_contextual(a)
    bb = _base_flexao_contextual(b)
    if aa == bb:
        return True
    if len(aa) == len(bb) and len(aa) >= 6 and aa[:-1] == bb[:-1] and {aa[-1], bb[-1]} <= {"a", "o"}:
        return True
    return False
'''
        txt = txt.replace(marker, helper + marker, 1)
        print("✅ Helper de flexões contextuais adicionado")

    fn_start = txt.find("def _corrupcao_lexical(")
    if fn_start == -1:
        fail("_corrupcao_lexical não encontrada")
    fn_end = txt.find("\ndef ", fn_start + 10)
    if fn_end == -1:
        fn_end = len(txt)
    block = txt[fn_start:fn_end]
    guard = '''            if _flexao_contextual_valida(base, original):\n                continue\n\n'''
    target = '''            if base[:3] != original[:3]:\n                continue\n'''
    if "_flexao_contextual_valida(base, original)" not in block:
        if target not in block:
            fail("ponto de inserção da flexão não encontrado")
        block = block.replace(target, guard + target, 1)
        txt = txt[:fn_start] + block + txt[fn_end:]
        print("✅ Plural/flexão legítima não gera corrupção lexical")
    else:
        print("ℹ️ Guarda de flexão já ativa")
    STRUCTURAL.write_text(txt, encoding="utf-8")

    # 4) Parser Qwen tolerante a aliases/typos de chaves.
    txt = GENERATOR.read_text(encoding="utf-8")
    fn_start = txt.find("def normalizar_distratores_parciais(")
    if fn_start == -1:
        fail("normalizar_distratores_parciais não encontrada")
    fn_end = txt.find("\ndef ", fn_start + 10)
    if fn_end == -1:
        fn_end = len(txt)
    block = txt[fn_start:fn_end]

    if "HAILA_V14_PARSER_TOLERANTE" not in block:
        new_block = r'''def normalizar_distratores_parciais(data: Any) -> tuple[list[DistratorGerado], list[str]]:
    """Normaliza de zero a N candidatos; o contrato exato é aplicado acima."""
    normalizacoes: list[str] = []

    # HAILA_V14_PARSER_TOLERANTE
    if isinstance(data, dict):
        aliases = {
            "distratores", "distrator", "distratos",
            "distrators", "distrutores", "alternativas",
        }
        candidatos_brutos = []

        for chave, valor in data.items():
            chave_norm = re.sub(r"[^a-z]", "", str(chave).casefold())
            eh_alias = chave_norm in aliases
            eh_variacao = chave_norm.startswith("distrat") or chave_norm.startswith("distor")
            campo_correto = "corret" in chave_norm or "gabarit" in chave_norm or "answer" in chave_norm

            if isinstance(valor, list) and (eh_alias or eh_variacao) and not campo_correto:
                candidatos_brutos.extend(valor)
                if chave != "distratores":
                    normalizacoes.append(f"{chave}->distratores")

        if candidatos_brutos:
            data = candidatos_brutos

    if not isinstance(data, list):
        raise ValueError("saída SLM não contém lista de distratores")

    saida = []
    for item in data:
        if isinstance(item, str):
            normalizacoes.append("string->objeto")
            item = {"texto": item}
        if not isinstance(item, dict):
            raise ValueError("distrator malformado")

        texto = item.get("texto") or item.get("distrator") or item.get("alternativa")
        if not texto:
            raise ValueError("distrator sem texto")

        texto = re.sub(r"\s+", " ", str(texto).replace("\\n", " ").strip())
        if not texto:
            continue

        saida.append(DistratorGerado(
            texto,
            str(item.get("erro", "")).strip(),
            str(item.get("por_que_e_falso", "")).strip(),
        ))

    return saida, normalizacoes
'''
        txt = txt[:fn_start] + new_block + txt[fn_end:]
        print("✅ Parser Qwen tolerante a distratodos/distortores")
    else:
        print("ℹ️ Parser tolerante já ativo")
    GENERATOR.write_text(txt, encoding="utf-8")

    # 5) Smoke test de Redes: um único alvo cognitivo (subnetting).
    txt = SMOKE.read_text(encoding="utf-8")
    old = (
        '"Avaliar se o estudante consegue selecionar o mecanismo de "\n'
        '                "endereçamento e roteamento adequado em uma situação de redes "\n'
        '                "IPv4 envolvendo sub-redes e encaminhamento de pacotes."'
    )
    new = (
        '"Avaliar se o estudante consegue calcular e selecionar o prefixo "\n'
        '                "IPv4 adequado para atender a uma necessidade de hosts ou "\n'
        '                "para dividir uma rede em sub-redes."'
    )
    if old in txt:
        txt = txt.replace(old, new, 1)
        print("✅ Smoke test de Redes agora avalia somente subnetting")
    elif "calcular e selecionar o prefixo" in txt:
        print("ℹ️ Smoke test de Redes já estava atômico")
    else:
        print("⚠️ Objetivo de Redes não foi alterado automaticamente")

    txt = txt.replace(
        '"habilidade": "Aplicar conceitos de endereçamento IPv4 e roteamento em uma situação-problema.",',
        '"habilidade": "Calcular o prefixo IPv4 adequado em uma situação de subnetting.",',
        1,
    )
    txt = txt.replace(
        '"objeto_conhecimento": "Endereçamento IPv4, sub-redes e roteamento.",',
        '"objeto_conhecimento": "Endereçamento IPv4, CIDR e subnetting.",',
        1,
    )

    old_restr = '''            "restricoes": [
                "Evitar cálculos excessivamente longos.",
                "Produzir alternativas plausíveis.",
                "Manter apenas uma alternativa correta."
            ],'''
    new_restr = '''            "restricoes": [
                "Avaliar somente subnetting; não combinar com roteamento, NAT, DHCP ou VLAN.",
                "O gabarito deve ser apenas um prefixo CIDR (/xx) ou uma máscara decimal IPv4 válida.",
                "Evitar cálculos excessivamente longos.",
                "Produzir alternativas plausíveis do mesmo tipo do gabarito.",
                "Manter apenas uma alternativa correta."
            ],'''
    if old_restr in txt:
        txt = txt.replace(old_restr, new_restr, 1)
    SMOKE.write_text(txt, encoding="utf-8")

    # 6) Testes de regressão.
    TEST.write_text('''from haila.contracts import DistratorGerado, NucleoQuestao
from haila.generator import normalizar_distratores_parciais
from haila.hybrid import MemoriaDistratoresCurados
from haila.structural import _corrupcao_lexical, avaliar_distratores


def codigos(flags):
    return {f.codigo for f in flags}


def nucleo(resposta):
    return NucleoQuestao(
        enunciado=(
            "Um sistema permite ao usuário confirmar um pedido. "
            "Qual classificação de requisito descreve essa exigência?"
        ),
        resposta_correta=resposta,
        explicacao="A exigência descreve comportamento observável do sistema.",
        competencia="Engenharia de requisitos",
        habilidade="Classificar requisitos",
        objeto_conhecimento="Requisitos funcionais e não funcionais",
    )


def test_memoria_curada_requisito_funcional():
    memoria = MemoriaDistratoresCurados(dataset="/arquivo/inexistente.jsonl")
    recuperado = memoria.recuperar("Requisito funcional")
    assert recuperado is not None
    ds, prov = recuperado
    textos = [d.texto for d in ds]
    assert len(textos) == 4
    assert "Requisito não funcional" in textos
    assert prov["modelo"] == "slm-memory-curated-v1"


def test_oposto_nao_e_parafrase_do_gabarito():
    n = nucleo("Requisito não funcional")
    ds = [
        DistratorGerado("Requisito funcional"),
        DistratorGerado("Regra de negócio"),
        DistratorGerado("Restrição de projeto"),
        DistratorGerado("Critério de aceitação"),
    ]
    assert "distrator_parafraseia_gabarito" not in codigos(avaliar_distratores(n, ds))


def test_plural_requisitos_nao_e_corrupcao_lexical():
    n = nucleo("Requisito funcional")
    assert _corrupcao_lexical(n, "Requisitos de segurança") is None


def test_parser_reune_chaves_malformadas_do_qwen():
    data = {
        "distratos": ["A"],
        "distratodos": ["B", "C"],
        "distortores": ["D"],
        "distrator_correto": ["NÃO USAR"],
    }
    ds, norm = normalizar_distratores_parciais(data)
    assert [d.texto for d in ds] == ["A", "B", "C", "D"]
    assert all(d.texto != "NÃO USAR" for d in ds)
    assert norm
''', encoding="utf-8")
    print("✅ Testes v14 adicionados")

    python = ROOT / ".venv/bin/python"
    print("\n=== SINTAXE ===")
    subprocess.run([
        str(python), "-m", "py_compile",
        str(HYBRID), str(STRUCTURAL), str(GENERATOR), str(SMOKE)
    ], check=True)
    print("✅ Sintaxe válida")

    print("\n=== PYTEST ===")
    subprocess.run([str(python), "-m", "pytest", "-q"], cwd=ROOT / "backend", check=True)

except Exception as exc:
    print("\n❌ PATCH V14 FALHOU:", exc)
    print("↩️ Restaurando backup...")
    for path in FILES:
        src = BACKUP / path.relative_to(ROOT)
        if src.exists():
            shutil.copy2(src, path)
    if TEST.exists():
        TEST.unlink()
    print("✅ Rollback concluído")
    raise

print("\n" + "=" * 78)
print("✅ PATCH V14 INSTALADO")
print("=" * 78)
print("- funcional × não funcional não são tratados como paráfrases")
print("- plurais legítimos não viram corrupção lexical")
print("- memória curada cobre classificação geral de requisitos")
print("- parser do Qwen recupera listas em chaves malformadas")
print("- smoke test de Redes mede somente subnetting")
print("Backup:", BACKUP)
