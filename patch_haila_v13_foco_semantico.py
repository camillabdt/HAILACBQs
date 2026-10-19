#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path.home() / "HAILA"
HYBRID = ROOT / "backend/haila/hybrid.py"
GENERATOR = ROOT / "backend/haila/generator.py"
STRUCTURAL = ROOT / "backend/haila/structural.py"
TEST = ROOT / "backend/tests/test_v13_foco_semantico.py"
FILES = (HYBRID, GENERATOR, STRUCTURAL)
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
BACKUP = ROOT.parent / f"HAILA-backup-v13-{STAMP}"


def abort(msg: str) -> None:
    raise RuntimeError(msg)


if not ROOT.is_dir():
    abort(f"não encontrei {ROOT}")
for path in FILES:
    if not path.is_file():
        abort(f"arquivo ausente: {path}")

BACKUP.mkdir(parents=True, exist_ok=True)
for path in FILES:
    dst = BACKUP / path.relative_to(ROOT)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)

print("=" * 78)
print("HAILA v13 — foco semântico + consistência de subnetting")
print("=" * 78)
print("Backup:", BACKUP)

try:
    # 1) Memória curada para categorias frequentes de requisitos.
    txt = HYBRID.read_text(encoding="utf-8")
    marker = "TAXONOMIAS_CURADAS = (\n"
    if marker not in txt:
        abort("TAXONOMIAS_CURADAS não encontrada em hybrid.py")

    grupos = [
        (
            '    ("Atributo de qualidade", "Requisito funcional", '
            '"Regra de negócio", "Requisito de interface", "Restrição de domínio"),\n'
        ),
        (
            '    ("Requisito de desempenho", "Requisito de segurança", '
            '"Requisito de usabilidade", "Requisito de confiabilidade", '
            '"Requisito de portabilidade"),\n'
        ),
    ]
    for grupo in grupos:
        primeira = grupo.split('"')[1]
        if f'("{primeira}",' not in txt:
            txt = txt.replace(marker, marker + grupo, 1)
            print(f"✅ Família curada adicionada: {primeira}")
        else:
            print(f"ℹ️ Família curada já existe: {primeira}")

    # A rota CIDR não deve transformar uma resposta combinada em alternativas só de prefixo.
    if "HAILA_V13_IPV4_SINGLE_FOCUS" not in txt:
        anchor = '    contexto = normalizar_texto(f"{enunciado} {resposta}")\n'
        addition = '''    # HAILA_V13_IPV4_SINGLE_FOCUS
    resposta_norm = normalizar_texto(resposta)
    if re.search(
        r"\\b(?:rota|roteamento|encaminhamento|gateway|ospf|rip|bgp|"
        r"estatica|estatico|dinamica|dinamico)\\b",
        resposta_norm,
    ):
        return None

    contexto = normalizar_texto(f"{enunciado} {resposta}")
'''
        if anchor not in txt:
            abort("ponto da rota IPv4 não encontrado em hybrid.py")
        txt = txt.replace(anchor, addition, 1)
        print("✅ Rota IPv4 limitada a um único foco")
    else:
        print("ℹ️ Guarda de foco IPv4 já existe")

    HYBRID.write_text(txt, encoding="utf-8")

    # 2) Núcleo: detectar questão multiconceito e gabarito de subnetting incorreto.
    txt = STRUCTURAL.read_text(encoding="utf-8")

    if "def _prefixo_ipv4_resposta(" not in txt:
        marker = "\ndef avaliar_nucleo("
        if marker not in txt:
            abort("avaliar_nucleo não encontrada em structural.py")
        helper = r'''

def _prefixo_ipv4_resposta(texto: str) -> int | None:
    achado = re.search(r"(?<!\d)/\s*(\d{1,2})(?!\d)", str(texto))
    if achado:
        valor = int(achado.group(1))
        return valor if 0 <= valor <= 32 else None

    func = globals().get("_prefixo_mascara_ipv4_qualidade")
    if callable(func):
        return func(str(texto))
    return None


def _numero_subredes_iguais(enunciado: str) -> tuple[int, int] | None:
    texto = _normalizar(enunciado)
    rede = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}/(\d{1,2})\b", str(enunciado))
    if not rede:
        return None

    nomes = {
        "duas": 2, "tres": 3, "quatro": 4, "cinco": 5,
        "seis": 6, "sete": 7, "oito": 8, "dezesseis": 16,
    }
    achado = re.search(
        r"\b(?:dividir|subdividir|segmentar|separar)\w*.{0,120}?"
        r"\b(?:em|para)\s+(\d+|duas|tres|quatro|cinco|seis|sete|oito|dezesseis)"
        r"\s+(?:sub\s*redes?|partes|blocos)\s+iguais\b",
        texto,
        re.I,
    )
    if not achado:
        return None

    bruto = achado.group(1)
    quantidade = int(bruto) if bruto.isdigit() else nomes.get(bruto)
    if not quantidade or quantidade < 2:
        return None
    return int(rede.group(1)), quantidade


def _prefixo_esperado_subredes_iguais(enunciado: str) -> int | None:
    dados = _numero_subredes_iguais(enunciado)
    if not dados:
        return None
    prefixo_base, quantidade = dados
    bits = 0
    capacidade = 1
    while capacidade < quantidade:
        capacidade *= 2
        bits += 1
    esperado = prefixo_base + bits
    return esperado if esperado <= 32 else None


def _resposta_ipv4_multiconceito(n: NucleoQuestao) -> bool:
    resposta = _normalizar(n.resposta_correta)
    enunciado = _normalizar(n.enunciado)
    tem_prefixo = _prefixo_ipv4_resposta(n.resposta_correta) is not None
    tem_roteamento = bool(re.search(
        r"\b(?:rota|roteamento|encaminhamento|gateway|ospf|rip|bgp|"
        r"estatica|estatico|dinamica|dinamico)\b",
        resposta,
    ))
    comando_duplo = bool(
        re.search(
            r"\b(?:enderecamento|mascara|sub\s*rede).{0,80}\b(?:e|com)\b"
            r".{0,80}\b(?:roteamento|encaminhamento|rota)\b",
            enunciado,
        )
        or re.search(
            r"\b(?:roteamento|encaminhamento|rota).{0,80}\b(?:e|com)\b"
            r".{0,80}\b(?:enderecamento|mascara|sub\s*rede)\b",
            enunciado,
        )
    )
    return tem_prefixo and (tem_roteamento or comando_duplo)
'''
        txt = txt.replace(marker, helper + marker, 1)
        print("✅ Validadores semânticos IPv4 adicionados")
    else:
        print("ℹ️ Validadores semânticos IPv4 já existem")

    if '"gabarito_ipv4_inconsistente"' not in txt:
        anchor = '''    resposta_norm = _normalizar(n.resposta_correta)
    enunciado_norm = _normalizar(n.enunciado)
'''
        addition = anchor + r'''
    if _resposta_ipv4_multiconceito(n):
        add(
            "questao_multiconceito",
            "enunciado",
            (
                "o item exige simultaneamente uma decisão de subnetting e uma decisão "
                "de roteamento; mantenha um único alvo cognitivo"
            ),
        )

    esperado_ipv4 = _prefixo_esperado_subredes_iguais(n.enunciado)
    resposta_ipv4 = _prefixo_ipv4_resposta(n.resposta_correta)
    if (
        esperado_ipv4 is not None
        and resposta_ipv4 is not None
        and esperado_ipv4 != resposta_ipv4
    ):
        add(
            "gabarito_ipv4_inconsistente",
            "resposta_correta",
            (
                f"para a subdivisão descrita, o prefixo esperado é /{esperado_ipv4}, "
                f"mas o gabarito usa /{resposta_ipv4}"
            ),
        )
'''
        if anchor not in txt:
            abort("ponto de inserção em avaliar_nucleo não encontrado")
        txt = txt.replace(anchor, addition, 1)
        print("✅ Red Flags de multiconceito e matemática IPv4 adicionadas")
    else:
        print("ℹ️ Red Flags v13 já existem")

    STRUCTURAL.write_text(txt, encoding="utf-8")

    # 3) Prompt e reparo do núcleo.
    txt = GENERATOR.read_text(encoding="utf-8")

    if "REGRA DE FOCO SEMÂNTICO V13" not in txt:
        pos = txt.find("\nINSTRUCAO_DISTRACTORES =")
        if pos == -1:
            abort("fim de SYSTEM_NUCLEO não localizado")
        before, after = txt[:pos], txt[pos:]
        needle = "Responda somente JSON válido.\n" + '"""'
        idx = before.rfind(needle)
        if idx == -1:
            abort("fechamento do SYSTEM_NUCLEO não localizado")
        regra = '''REGRA DE FOCO SEMÂNTICO V13:
Cada item deve avaliar UMA decisão principal. Não combine, no mesmo gabarito,
uma máscara/prefixo de sub-rede com uma técnica de roteamento, protocolo,
algoritmo ou outra decisão independente.

Em questões de subnetting com divisão em partes iguais, calcule o prefixo antes
de escrever resposta_correta e explicacao. Exemplo: dividir um /24 em quatro
sub-redes iguais exige emprestar 2 bits, resultando em /26.

Em Engenharia de Requisitos, mantenha o nível taxonômico consistente. Se o
comando pede classificação geral, use "Requisito funcional" ou "Requisito não
funcional". Se pede o tipo de atributo de qualidade, use categorias específicas,
como "Requisito de desempenho", "Requisito de segurança" ou equivalentes.

Responda somente JSON válido.
"""'''
        before = before[:idx] + regra + before[idx + len(needle):]
        txt = before + after
        print("✅ Prompt do núcleo reforçado com foco semântico")
    else:
        print("ℹ️ Regra de foco semântico já existe")

    if 'if "questao_multiconceito" in codigos:' not in txt:
        anchor = '        if "iwf_termo_absoluto" in codigos:\n'
        repair = '''        if "questao_multiconceito" in codigos:
            reparo_prioritario += (
                "CORREÇÃO OBRIGATÓRIA: avalie apenas UMA decisão. "
                "Se o item for de subnetting, pergunte somente pela máscara/prefixo. "
                "Não combine subnetting com roteamento no mesmo gabarito. "
            )

        if "gabarito_ipv4_inconsistente" in codigos:
            reparo_prioritario += (
                "CORREÇÃO OBRIGATÓRIA: refaça o cálculo de subnetting antes de "
                "escrever o gabarito e confira a explicação matematicamente. "
            )

''' + anchor
        if anchor not in txt:
            abort("ponto de reparo prioritário não encontrado")
        txt = txt.replace(anchor, repair, 1)
        print("✅ Feedback de regeneração do núcleo atualizado")
    else:
        print("ℹ️ Feedback v13 já existe")

    GENERATOR.write_text(txt, encoding="utf-8")

    # 4) Testes de regressão.
    TEST.write_text('''from haila.contracts import NucleoQuestao\nfrom haila.hybrid import MemoriaDistratoresCurados, gerar_distratores_ipv4_cidr\nfrom haila.structural import avaliar_nucleo\n\n\ndef codes(n):\n    return {f.codigo for f in avaliar_nucleo(n)}\n\n\ndef nucleo(enunciado, resposta):\n    return NucleoQuestao(\n        enunciado=enunciado,\n        resposta_correta=resposta,\n        explicacao="Explicação tecnicamente consistente.",\n        competencia="Redes de computadores",\n        habilidade="Aplicar conceitos",\n        objeto_conhecimento="IPv4",\n    )\n\n\ndef test_memoria_reconhece_atributo_de_qualidade():\n    memoria = MemoriaDistratoresCurados(dataset="/arquivo/inexistente.jsonl")\n    recuperado = memoria.recuperar("Atributo de qualidade")\n    assert recuperado is not None\n    ds, prov = recuperado\n    textos = [d.texto for d in ds]\n    assert len(textos) == 4\n    assert "Requisito funcional" in textos\n    assert "Requisito de desempenho" not in textos\n    assert prov["modelo"] == "slm-memory-curated-v1"\n\n\ndef test_subdivisao_quatro_partes_de_24_exige_26():\n    n = nucleo(\n        "Uma empresa possui a rede IPv4 200.100.50.0/24 e pretende dividir "\n        "o bloco em quatro sub-redes iguais. Qual prefixo deve usar?",\n        "/27",\n    )\n    assert "gabarito_ipv4_inconsistente" in codes(n)\n\n\ndef test_subdivisao_quatro_partes_de_24_aceita_26():\n    n = nucleo(\n        "Uma empresa possui a rede IPv4 200.100.50.0/24 e pretende dividir "\n        "o bloco em quatro sub-redes iguais. Qual prefixo deve usar?",\n        "/26",\n    )\n    assert "gabarito_ipv4_inconsistente" not in codes(n)\n\n\ndef test_bloqueia_resposta_ipv4_com_duas_decisoes():\n    n = nucleo(\n        "Uma empresa possui a rede IPv4 200.100.50.0/24 e pretende dividir "\n        "o bloco em quatro sub-redes iguais e configurar o encaminhamento para "\n        "uma rede externa. Qual mecanismo de endereçamento e roteamento deve ser usado?",\n        "CIDR /26 com rota fixa",\n    )\n    assert "questao_multiconceito" in codes(n)\n\n\ndef test_rota_ipv4_nao_transforma_resposta_combinada_em_prefixos():\n    ds = gerar_distratores_ipv4_cidr(\n        "CIDR /26 com rota fixa",\n        "Uma rede IPv4 será subdividida.",\n    )\n    assert ds is None\n''', encoding="utf-8")
    print("✅ Testes v13 adicionados")

    python = ROOT / ".venv/bin/python"
    print("\n=== SINTAXE ===")
    subprocess.run([str(python), "-m", "py_compile", *map(str, FILES)], check=True)
    print("✅ Sintaxe válida")

    print("\n=== PYTEST ===")
    subprocess.run([str(python), "-m", "pytest", "-q"], cwd=ROOT / "backend", check=True)

except Exception as exc:
    print("\n❌ PATCH V13 FALHOU:", exc)
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
print("✅ PATCH V13 INSTALADO")
print("=" * 78)
print("- 'Atributo de qualidade' usa memória curada")
print("- questões IPv4 multiconceito são regeneradas")
print("- subdivisão IPv4 em partes iguais tem checagem matemática")
print("- rota determinística IPv4 não aceita resposta combinada")
print("Backup:", BACKUP)
