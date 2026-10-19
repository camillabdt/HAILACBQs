#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path.home() / "HAILA"
HYBRID = ROOT / "backend/haila/hybrid.py"
GENERATOR = ROOT / "backend/haila/generator.py"
STRUCTURAL = ROOT / "backend/haila/structural.py"
REDFLAGS = ROOT / "backend/haila/redflags.py"
TEST = ROOT / "backend/tests/test_v12_consolidado.py"

STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
BACKUP = ROOT.parent / f"HAILA-backup-v12-{STAMP}"

FILES = (HYBRID, GENERATOR, STRUCTURAL, REDFLAGS)


def die(msg: str) -> None:
    print(f"❌ {msg}")
    sys.exit(1)


if not ROOT.is_dir():
    die(f"não encontrei {ROOT}")

for path in FILES:
    if not path.is_file():
        die(f"arquivo ausente: {path}")

BACKUP.mkdir(parents=True, exist_ok=True)
for path in FILES:
    dst = BACKUP / path.relative_to(ROOT)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)

print("=" * 76)
print("HAILA v12 — consolidação de roteamento e qualidade")
print("=" * 76)
print("Backup:", BACKUP)

try:
    # ==============================================================
    # 1) HYBRID: memória curada de requisitos + IPv4 decimal/CIDR
    # ==============================================================
    txt = HYBRID.read_text(encoding="utf-8")

    req_group = (
        '    ("Requisito não funcional", "Requisito funcional", '
        '"Regra de negócio", "Requisito de interface", "Restrição de domínio"),\n'
    )
    if '"Requisito não funcional", "Requisito funcional"' not in txt:
        anchor = (
            '    ("Não funcional", "Funcional", "Regra de negócio", '
            '"Requisito de interface", "Restrição de domínio"),\n'
        )
        if anchor in txt:
            txt = txt.replace(anchor, anchor + req_group, 1)
        else:
            marker = "TAXONOMIAS_CURADAS = (\n"
            if marker not in txt:
                raise RuntimeError("TAXONOMIAS_CURADAS não encontrada")
            txt = txt.replace(marker, marker + req_group, 1)
        print("✅ Memória curada de requisitos adicionada")
    else:
        print("ℹ️ Memória curada de requisitos já existe")

    if "def _prefixo_de_mascara_decimal_ipv4(" not in txt:
        marker = "\ndef gerar_distratores_ipv4_cidr("
        if marker not in txt:
            raise RuntimeError("gerar_distratores_ipv4_cidr não encontrada")
        helper = r'''

def _prefixo_de_mascara_decimal_ipv4(texto: str) -> int | None:
    achado = re.search(r"\b((?:\d{1,3}\.){3}\d{1,3})\b", str(texto))
    if not achado:
        return None

    partes = [int(x) for x in achado.group(1).split(".")]
    if any(x < 0 or x > 255 for x in partes):
        return None

    valor = 0
    for octeto in partes:
        valor = (valor << 8) | octeto

    bits = f"{valor:032b}"
    if "01" in bits:
        return None

    return bits.count("1")
'''
        txt = txt.replace(marker, helper + marker, 1)
        print("✅ Conversor máscara decimal -> prefixo adicionado")
    else:
        print("ℹ️ Conversor de máscara decimal já existe")

    old = '''    achado = re.search(r"(?<!\\d)/\\s*(\\d{1,2})(?!\\d)", str(resposta))
    if not achado:
        return None

    correto = int(achado.group(1))
    if not 1 <= correto <= 30:
        return None
'''
    new = '''    achado = re.search(r"(?<!\\d)/\\s*(\\d{1,2})(?!\\d)", str(resposta))
    if achado:
        correto = int(achado.group(1))
    else:
        correto = _prefixo_de_mascara_decimal_ipv4(str(resposta))
        if correto is None:
            return None

    if not 1 <= correto <= 30:
        return None
'''

    if old in txt:
        txt = txt.replace(old, new, 1)
        print("✅ Rota IPv4 agora reconhece gabarito em CIDR ou máscara decimal")
    elif "_prefixo_de_mascara_decimal_ipv4(str(resposta))" in txt:
        print("ℹ️ Rota IPv4 decimal já estava ativa")
    else:
        raise RuntimeError("não encontrei bloco de extração do prefixo em hybrid.py")

    HYBRID.write_text(txt, encoding="utf-8")

    # ==============================================================
    # 2) GENERATOR: plural legítimo + parser singular "distrator"
    # ==============================================================
    txt = GENERATOR.read_text(encoding="utf-8")

    target = '''            if base[:3] != original[:3]:
                continue
'''
    replacement = '''            if _flexao_simples(base, original):
                continue

            if base[:3] != original[:3]:
                continue
'''

    # Insere somente dentro do filtro antigo, antes da primeira ocorrência
    # posterior à função motivo_distrator_lexicalmente_suspeito.
    fn_pos = txt.find("def motivo_distrator_lexicalmente_suspeito(")
    if fn_pos == -1:
        raise RuntimeError("filtro lexical não encontrado em generator.py")
    next_pos = txt.find("\ndef ", fn_pos + 10)
    if next_pos == -1:
        next_pos = len(txt)
    block = txt[fn_pos:next_pos]

    if "_flexao_simples(base, original)" not in block:
        if target not in block:
            raise RuntimeError("ponto do filtro de flexão não encontrado")
        block = block.replace(target, replacement, 1)
        txt = txt[:fn_pos] + block + txt[next_pos:]
        print("✅ Plural/flexão legítima deixou de ser tratada como corrupção")
    else:
        print("ℹ️ Exceção de flexão já existe no pré-filtro")

    old_keys = '("distratores", "distratos", "distrators", "distrutores", "alternativas")'
    new_keys = '("distratores", "distrator", "distratos", "distrators", "distrutores", "alternativas")'
    if old_keys in txt:
        txt = txt.replace(old_keys, new_keys, 1)
        print("✅ Parser agora aceita {'distrator': [...]} também")
    elif new_keys in txt:
        print("ℹ️ Parser singular já estava ativo")
    else:
        raise RuntimeError("lista de chaves do parser não encontrada")

    GENERATOR.write_text(txt, encoding="utf-8")

    # ==============================================================
    # 3) STRUCTURAL: barreira matemática para máscaras IPv4
    # ==============================================================
    txt = STRUCTURAL.read_text(encoding="utf-8")

    if "def _prefixo_mascara_ipv4_qualidade(" not in txt:
        marker = "\ndef avaliar_distratores("
        if marker not in txt:
            raise RuntimeError("avaliar_distratores não encontrada")
        helper = r'''

def _prefixo_mascara_ipv4_qualidade(texto: str) -> int | None:
    achado = re.search(r"\b((?:\d{1,3}\.){3}\d{1,3})\b", str(texto))
    if not achado:
        return None

    partes = [int(x) for x in achado.group(1).split(".")]
    if any(x < 0 or x > 255 for x in partes):
        return None

    valor = 0
    for octeto in partes:
        valor = (valor << 8) | octeto

    bits = f"{valor:032b}"
    if "01" in bits:
        return None

    return bits.count("1")


def _parece_mascara_ipv4(texto: str) -> bool:
    return bool(
        re.search(
            r"\b[0-9OoIl]{1,3}(?:\.[0-9OoIl]{1,3}){3}\b",
            str(texto),
        )
    )
'''
        txt = txt.replace(marker, helper + marker, 1)
        print("✅ Validador matemático de máscara IPv4 adicionado")
    else:
        print("ℹ️ Validador IPv4 já existe")

    if '"mascara_ipv4_invalida"' not in txt:
        anchor = '''    if any(_combinacao_invalida(t) for t in textos):
        add("combinacao_de_itens_invalida", "distratores", "há item romano repetido na alternativa")
'''
        addition = r'''    contexto_ipv4 = _normalizar(
        f"{n.enunciado} {n.resposta_correta}"
    )
    resposta_prefixo = _prefixo_mascara_ipv4_qualidade(n.resposta_correta)
    resposta_cidr = re.search(r"(?<!\d)/\s*(\d{1,2})(?!\d)", n.resposta_correta)
    if resposta_prefixo is None and resposta_cidr:
        resposta_prefixo = int(resposta_cidr.group(1))

    if resposta_prefixo is not None and any(
        termo in contexto_ipv4
        for termo in ("ipv4", "mascara", "sub rede", "cidr", "hosts")
    ):
        invalidas = []
        equivalentes = []
        tipo_incompativel = []

        for i, texto in enumerate(textos):
            cidr = re.search(r"(?<!\d)/\s*(\d{1,2})(?!\d)", texto)
            prefixo = int(cidr.group(1)) if cidr else _prefixo_mascara_ipv4_qualidade(texto)

            if _parece_mascara_ipv4(texto) and prefixo is None:
                invalidas.append((i, texto))
                continue

            if prefixo is None:
                tipo_incompativel.append((i, texto))
                continue

            if prefixo == resposta_prefixo:
                equivalentes.append((i, texto))

        if invalidas:
            add(
                "mascara_ipv4_invalida",
                "distratores",
                "; ".join(f'{i}:"{texto}"' for i, texto in invalidas),
            )

        if equivalentes:
            add(
                "mascara_ipv4_equivalente_ao_gabarito",
                "distratores",
                "; ".join(f'{i}:"{texto}"' for i, texto in equivalentes),
            )

        if tipo_incompativel:
            add(
                "distrator_tipo_incompativel_ipv4",
                "distratores",
                "; ".join(f'{i}:"{texto}"' for i, texto in tipo_incompativel),
            )

    if any(_combinacao_invalida(t) for t in textos):
        add("combinacao_de_itens_invalida", "distratores", "há item romano repetido na alternativa")
'''
        if anchor not in txt:
            raise RuntimeError("ponto de inserção IPv4 em structural.py não encontrado")
        txt = txt.replace(anchor, addition, 1)
        print("✅ Barreiras de máscara inválida/equivalente/tipo incompatível adicionadas")
    else:
        print("ℹ️ Barreiras IPv4 já existem")

    STRUCTURAL.write_text(txt, encoding="utf-8")

    # ==============================================================
    # 4) REDFLAGS: longest-option somente quando único maior
    # ==============================================================
    txt = REDFLAGS.read_text(encoding="utf-8")

    old = (
        "            if tamanhos and tamanhos[correta] == max(tamanhos) "
        "and tamanhos[correta] >= min(tamanhos) + 2:\n"
    )
    new = (
        "            if (\n"
        "                tamanhos\n"
        "                and tamanhos[correta] == max(tamanhos)\n"
        "                and tamanhos.count(tamanhos[correta]) == 1\n"
        "                and tamanhos[correta] >= min(tamanhos) + 2\n"
        "            ):\n"
    )
    if "tamanhos.count(tamanhos[correta]) == 1" not in txt:
        if old not in txt:
            raise RuntimeError("regra iwf_gabarito_mais_longo não encontrada")
        txt = txt.replace(old, new, 1)
        print("✅ IWF 'gabarito mais longo' corrigido para exigir destaque único")
    else:
        print("ℹ️ IWF de extensão já estava corrigido")

    REDFLAGS.write_text(txt, encoding="utf-8")

    # ==============================================================
    # 5) Testes de regressão
    # ==============================================================
    test_text = '''from haila.contracts import DistratorGerado, NucleoQuestao
from haila.generator import normalizar_distratores_parciais
from haila.hybrid import (
    MemoriaDistratoresCurados,
    gerar_distratores_ipv4_cidr,
)
from haila.redflags import DeterministicRedFlagAnalyzer
from haila.structural import avaliar_distratores


def codes(flags):
    return {f.codigo for f in flags}


def test_memoria_requisito_nao_funcional():
    memoria = MemoriaDistratoresCurados(dataset="/arquivo/inexistente.jsonl")
    recuperado = memoria.recuperar("Requisito não funcional")
    assert recuperado is not None
    ds, prov = recuperado
    textos = [d.texto for d in ds]
    assert len(textos) == 4
    assert "Requisito funcional" in textos
    assert "Regra de negócio" in textos
    assert prov["modelo"] == "slm-memory-curated-v1"


def test_ipv4_decimal_aciona_regra_deterministica():
    ds = gerar_distratores_ipv4_cidr(
        "255.255.255.0",
        "Uma rede IPv4 precisa atender até 200 hosts.",
    )
    assert ds is not None
    assert len(ds) == 4
    assert all("." in d.texto for d in ds)
    assert all(d.texto != "255.255.255.0" for d in ds)


def test_parser_aceita_chave_distrator_singular():
    ds, norm = normalizar_distratores_parciais({
        "distrator": ["A", "B", "C", "D"]
    })
    assert [d.texto for d in ds] == ["A", "B", "C", "D"]
    assert "distrator->distratores" in norm


def test_barreira_rejeita_mascaras_ipv4_corrompidas():
    n = NucleoQuestao(
        enunciado="Qual máscara IPv4 atende uma sub-rede para 200 hosts?",
        resposta_correta="255.255.255.0",
        explicacao="A máscara /24 oferece 254 hosts utilizáveis.",
        competencia="Redes",
        habilidade="Aplicar subnetting",
        objeto_conhecimento="IPv4",
    )
    ds = [
        DistratorGerado("254.248.0.OO"),
        DistratorGerado("254.248.00.1"),
        DistratorGerado("None of the above"),
        DistratorGerado("192.08.1.0"),
    ]
    c = codes(avaliar_distratores(n, ds))
    assert "mascara_ipv4_invalida" in c or "distrator_tipo_incompativel_ipv4" in c


def test_iwf_empate_no_maior_tamanho_nao_bloqueia():
    q = {
        "enunciado": "Qual categoria melhor classifica a restrição apresentada?",
        "alternativas": [
            "Tecnologia base",
            "Especificações técnicas",
            "Método de teste",
            "Definição de projeto",
            "Requisito não funcional",
        ],
        "correta": 4,
    }
    flags, _ = DeterministicRedFlagAnalyzer()(q, {}, {})
    assert "iwf_gabarito_mais_longo" not in codes(flags)
'''
    TEST.write_text(test_text, encoding="utf-8")
    print("✅ Testes v12 adicionados")

    python = ROOT / ".venv/bin/python"

    print("\n=== SINTAXE ===")
    subprocess.run(
        [str(python), "-m", "py_compile", *map(str, FILES)],
        check=True,
    )
    print("✅ Sintaxe válida")

    print("\n=== PYTEST ===")
    subprocess.run(
        [str(python), "-m", "pytest", "-q"],
        cwd=ROOT / "backend",
        check=True,
    )

except Exception as exc:
    print("\n❌ PATCH V12 FALHOU:", exc)
    print("↩️ Restaurando backup...")
    for path in FILES:
        src = BACKUP / path.relative_to(ROOT)
        if src.exists():
            shutil.copy2(src, path)
    if TEST.exists():
        TEST.unlink()
    print("✅ Rollback concluído")
    raise

print("\n" + "=" * 76)
print("✅ PATCH V12 INSTALADO")
print("=" * 76)
print("Ativo agora:")
print("- Requisito não funcional -> memória curada")
print("- IPv4 /CIDR ou máscara decimal -> regra determinística")
print("- máscara IPv4 inválida não chega ao item final")
print("- parser aceita chave 'distrator'")
print("- plurais legítimos não são descartados como corrupção")
print("- IWF longest-option exige gabarito unicamente mais longo")
print("Backup:", BACKUP)
