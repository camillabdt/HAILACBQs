#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path.home() / "HAILA"
HAILA = ROOT / "backend" / "haila"
PYTHON = ROOT / ".venv" / "bin" / "python"
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
BACKUP = ROOT.parent / f"HAILA-backup-ipv4-filtro-{STAMP}"


def must_replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"❌ Não encontrei o ponto para {label}. Nada desse passo foi aplicado.")
    return text.replace(old, new, 1)


print("=" * 72)
print("HAILA — rota IPv4 determinística + filtro lexical final")
print("=" * 72)

if not ROOT.is_dir():
    raise SystemExit(f"❌ Não encontrei {ROOT}")
if not PYTHON.exists():
    raise SystemExit(f"❌ Não encontrei {PYTHON}")

arquivos = [
    HAILA / "hybrid.py",
    HAILA / "generator.py",
    HAILA / "structural.py",
]

BACKUP.mkdir(parents=True, exist_ok=True)
for src in arquivos:
    if not src.exists():
        raise SystemExit(f"❌ Arquivo não encontrado: {src}")
    dst = BACKUP / src.relative_to(ROOT)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
print(f"✅ Backup: {BACKUP}")

# ---------------------------------------------------------------------
# hybrid.py: rota determinística para respostas CIDR/máscara IPv4
# ---------------------------------------------------------------------
hybrid = HAILA / "hybrid.py"
t = hybrid.read_text(encoding="utf-8")

if "def gerar_distratores_ipv4_cidr(" not in t:
    anchor = "\n\nclass HybridDistractorGenerator:"
    helper = r'''


def _mascara_decimal_ipv4(prefixo: int) -> str:
    if not 0 <= prefixo <= 32:
        raise ValueError("prefixo IPv4 inválido")
    valor = ((0xFFFFFFFF << (32 - prefixo)) & 0xFFFFFFFF) if prefixo else 0
    return ".".join(
        str((valor >> deslocamento) & 0xFF)
        for deslocamento in (24, 16, 8, 0)
    )


def gerar_distratores_ipv4_cidr(
    resposta: str,
    enunciado: str = "",
) -> list[DistratorGerado] | None:
    """Rota determinística para alternativas de prefixo/máscara IPv4."""
    contexto = normalizar_texto(f"{enunciado} {resposta}")
    marcadores = (
        "ipv4", "cidr", "sub-rede", "subrede", "mascara",
        "prefixo", "hosts", "enderecos", "enderecamento",
    )
    if not any(m in contexto for m in marcadores):
        return None

    achado = re.search(r"(?<!\\d)/\\s*(\\d{1,2})(?!\\d)", str(resposta))
    if not achado:
        return None

    correto = int(achado.group(1))
    if not 1 <= correto <= 30:
        return None

    prefixos: list[int] = []
    for delta in (-1, 1, -2, 2, -3, 3, -4, 4, -5, 5):
        p = correto + delta
        if 1 <= p <= 30 and p != correto and p not in prefixos:
            prefixos.append(p)
        if len(prefixos) == 4:
            break
    if len(prefixos) != 4:
        return None

    resposta_tem_decimal = bool(
        re.search(r"\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b", str(resposta))
    )
    saida: list[DistratorGerado] = []
    for p in prefixos:
        texto = f"/{p}"
        if resposta_tem_decimal:
            texto = f"Máscara /{p} ({_mascara_decimal_ipv4(p)})"
        saida.append(
            DistratorGerado(
                texto,
                "prefixo_ipv4_incorreto",
                f"o prefixo /{p} oferece capacidade diferente da requerida",
            )
        )
    return saida
'''
    helper = helper.replace("\\\\", "\\")
    t = must_replace(t, anchor, helper + anchor, "inserir gerador IPv4")
    print("✅ Função determinística IPv4 adicionada")
else:
    print("ℹ️ Função determinística IPv4 já existe")

if '"modelo": "deterministic-ipv4-cidr-v1"' not in t:
    old = (
        "    def __call__(self, nucleo: NucleoQuestao, feedback):\n"
        "        familia = classificar_familia(nucleo.resposta_correta, nucleo.enunciado)\n"
    )
    new = (
        "    def __call__(self, nucleo: NucleoQuestao, feedback):\n"
        "        if self.use_rules:\n"
        "            ipv4 = gerar_distratores_ipv4_cidr(\n"
        "                nucleo.resposta_correta,\n"
        "                nucleo.enunciado,\n"
        "            )\n"
        "            if ipv4:\n"
        "                return ipv4, {\n"
        '                    "modelo": "deterministic-ipv4-cidr-v1",\n'
        '                    "familia": "ipv4_cidr",\n'
        '                    "roteador": "hybrid-v9",\n'
        '                    "estrategia": "prefixos_vizinhos_validos",\n'
        "                }\n"
        "\n"
        "        familia = classificar_familia(nucleo.resposta_correta, nucleo.enunciado)\n"
    )
    t = must_replace(t, old, new, "ativar rota IPv4")

    t = t.replace(
        'modo = "hybrid-v8" if self.use_memory or self.use_rules else "slm-only-v1"',
        'modo = "hybrid-v9" if self.use_memory or self.use_rules else "slm-only-v1"',
        1,
    )
    t = t.replace('roteador="hybrid-v8"', 'roteador="hybrid-v9"')
    print("✅ Rota IPv4 ativada antes do Qwen")
else:
    print("ℹ️ Rota IPv4 já estava ativa")

hybrid.write_text(t, encoding="utf-8")

# ---------------------------------------------------------------------
# generator.py: filtro pós-geração, independente do filtro Qwen existente
# ---------------------------------------------------------------------
generator = HAILA / "generator.py"
t = generator.read_text(encoding="utf-8")

if "from difflib import SequenceMatcher" not in t:
    if "import unicodedata\n" in t:
        t = t.replace(
            "import unicodedata\n",
            "import unicodedata\nfrom difflib import SequenceMatcher\n",
            1,
        )
    else:
        t = "from difflib import SequenceMatcher\n" + t

if "def _motivo_candidato_pos_filtro(" not in t:
    anchor = "\n\nclass BestOfNDistractorGenerator:"
    helper = r'''


def _token_qualidade(texto: str) -> str:
    base = unicodedata.normalize("NFKD", str(texto).casefold())
    base = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", base)


def _base_flexao_portugues(token: str) -> str:
    # Plurais frequentes suficientes para não tratar flexão como corrupção.
    # Ex.: requisito/requisitos e funcional/funcionais.
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


def _flexao_simples(a: str, b: str) -> bool:
    return _base_flexao_portugues(a) == _base_flexao_portugues(b)


def _motivo_candidato_pos_filtro(nucleo, texto: str) -> str | None:
    bruto = str(texto).strip()
    if re.search(r"^\\s*(?:\\([A-E]\\)|[A-E][\\)\\].:\\-])\\s*", bruto, re.I):
        return "rotulo_de_alternativa_embutido"

    tokens_candidato = re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_-]*", bruto)
    tokens_gabarito = re.findall(
        r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_-]*",
        str(nucleo.resposta_correta),
    )
    bases_gabarito = [_token_qualidade(x) for x in tokens_gabarito]

    for token in tokens_candidato:
        base = _token_qualidade(token)
        if len(base) < 6:
            continue
        for origem in bases_gabarito:
            if len(origem) < 6 or base == origem:
                continue
            if _flexao_simples(base, origem):
                continue
            if base[:4] != origem[:4]:
                continue
            if abs(len(base) - len(origem)) > 4:
                continue
            sim = SequenceMatcher(None, base, origem).ratio()
            if sim >= 0.80:
                return (
                    f'possivel_deformacao_lexical:{token}~{origem}:'
                    f'{sim:.2f}'
                )
    return None


def _filtrar_pool_final(nucleo, candidatos):
    validos = []
    rejeitados = []
    for candidato in candidatos:
        motivo = _motivo_candidato_pos_filtro(nucleo, candidato.texto)
        if motivo:
            rejeitados.append({"texto": candidato.texto, "motivo": motivo})
        else:
            validos.append(candidato)
    return validos, rejeitados
'''
    helper = helper.replace("\\\\", "\\")
    t = must_replace(t, anchor, helper + anchor, "inserir filtro pós-geração")
    print("✅ Filtro pós-geração adicionado")
else:
    print("ℹ️ Filtro pós-geração já existe")

old = (
    "    def __call__(self, nucleo, feedback):\n"
    "        candidatos, provenance = self.generator(nucleo, feedback)\n"
    "        if len(candidatos) == 4:\n"
    "            return candidatos, dict(provenance, selecao=\"pool_exato\")\n"
)
new = (
    "    def __call__(self, nucleo, feedback):\n"
    "        candidatos, provenance = self.generator(nucleo, feedback)\n"
    "        candidatos, rejeitados_pos_filtro = _filtrar_pool_final(nucleo, candidatos)\n"
    "        if rejeitados_pos_filtro:\n"
    "            provenance = dict(\n"
    "                provenance,\n"
    "                pos_filtro_rejeitados=rejeitados_pos_filtro,\n"
    "            )\n"
    "        if len(candidatos) < 4:\n"
    "            raise ValueError(\n"
    "                \"pool insuficiente após filtro de qualidade; \"\n"
    "                f\"validos={len(candidatos)}; rejeitados={rejeitados_pos_filtro}\"\n"
    "            )\n"
    "        if len(candidatos) == 4:\n"
    "            return candidatos, dict(provenance, selecao=\"pool_exato\")\n"
)
if "pos_filtro_rejeitados" not in t:
    t = must_replace(t, old, new, "ativar filtro em BestOfN")
    print("✅ BestOfN agora filtra rótulos/deformações antes de selecionar")
else:
    print("ℹ️ BestOfN já usa o pós-filtro")

generator.write_text(t, encoding="utf-8")

# ---------------------------------------------------------------------
# structural.py: última barreira para rótulo e deformação do gabarito
# ---------------------------------------------------------------------
structural = HAILA / "structural.py"
t = structural.read_text(encoding="utf-8")

if "def _deformacao_lexical_do_gabarito(" not in t:
    anchor = "\n\ndef avaliar_distratores("
    helper = r'''


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
'''
    helper = helper.replace("\\\\", "\\")
    t = must_replace(t, anchor, helper + anchor, "inserir verificação lexical estrutural")

if '"distrator_com_rotulo_embutido"' not in t:
    old = "    textos = [d.texto.strip() for d in distratores]\n"
    new = (
        "    textos = [d.texto.strip() for d in distratores]\n"
        "    rotulados = [\n"
        "        (i, texto) for i, texto in enumerate(textos)\n"
        "        if re.search(r\"^\\s*(?:\\([A-E]\\)|[A-E][\\)\\].:\\-])\\s*\", texto, re.I)\n"
        "    ]\n"
        "    if rotulados:\n"
        "        add(\n"
        '            "distrator_com_rotulo_embutido",\n'
        '            "distratores",\n'
        "            \"; \".join(f'{i}:{texto}' for i, texto in rotulados),\n"
        "        )\n"
        "    deformados = [\n"
        "        (i, texto, _deformacao_lexical_do_gabarito(n.resposta_correta, texto))\n"
        "        for i, texto in enumerate(textos)\n"
        "    ]\n"
        "    deformados = [x for x in deformados if x[2]]\n"
        "    if deformados:\n"
        "        add(\n"
        '            "distrator_lexicalmente_corrompido",\n'
        '            "distratores",\n'
        "            \"; \".join(f'{i}:{texto}:{motivo}' for i, texto, motivo in deformados),\n"
        "        )\n"
    )
    new = new.replace("\\\\", "\\")
    t = must_replace(t, old, new, "ativar barreiras estruturais de distrator")
    print("✅ Barreiras finais de qualidade adicionadas")
else:
    print("ℹ️ Barreiras finais já existem")

structural.write_text(t, encoding="utf-8")

# ---------------------------------------------------------------------
# Testes do patch
# ---------------------------------------------------------------------
test_path = ROOT / "backend" / "tests" / "test_ipv4_route_and_filter.py"
test_path.write_text(
    '''from haila.contracts import NucleoQuestao\n'''
    '''from haila.hybrid import gerar_distratores_ipv4_cidr\n'''
    '''from haila.generator import _motivo_candidato_pos_filtro\n'''
    '''\n'''
    '''def _nucleo(gabarito):\n'''
    '''    return NucleoQuestao(\n'''
    '''        "Em uma rede IPv4, escolha o prefixo CIDR adequado para 30 hosts.",\n'''
    '''        gabarito,\n'''
    '''        "Explicação suficiente para o teste.",\n'''
    '''        "Redes",\n'''
    '''        "Aplicar subnetting",\n'''
    '''        "IPv4 e CIDR",\n'''
    '''    )\n'''
    '''\n'''
    '''def test_ipv4_prefixo_curto():\n'''
    '''    ds = gerar_distratores_ipv4_cidr("/27", "Rede IPv4 para 30 hosts")\n'''
    '''    assert ds is not None and len(ds) == 4\n'''
    '''    assert "/27" not in [d.texto for d in ds]\n'''
    '''    assert len({d.texto for d in ds}) == 4\n'''
    '''\n'''
    '''def test_ipv4_mascara_decimal():\n'''
    '''    ds = gerar_distratores_ipv4_cidr(\n'''
    '''        "Máscara /28 (255.255.255.240)",\n'''
    '''        "Subnetting IPv4",\n'''
    '''    )\n'''
    '''    assert ds is not None and len(ds) == 4\n'''
    '''    assert all("Máscara /" in d.texto for d in ds)\n'''
    '''\n'''
    '''def test_plural_regular_nao_e_corrupcao():\n'''
    '''    n = _nucleo("Requisito não funcional")\n'''
    '''    assert _motivo_candidato_pos_filtro(n, "Requisitos funcionais") is None\n'''
    '''\n'''
    '''def test_requisitorios_e_rejeitado():\n'''
    '''    n = _nucleo("Requisito não funcional")\n'''
    '''    assert _motivo_candidato_pos_filtro(n, "Requisitórios") is not None\n'''
    '''\n'''
    '''def test_rotulo_embutido_e_rejeitado():\n'''
    '''    n = _nucleo("Requisito não funcional")\n'''
    '''    assert _motivo_candidato_pos_filtro(n, "(D) Definição de projeto") is not None\n''',
    encoding="utf-8",
)
print(f"✅ Testes novos: {test_path}")

print("\n=== SINTAXE ===")
subprocess.run(
    [
        str(PYTHON), "-m", "py_compile",
        str(hybrid), str(generator), str(structural),
    ],
    check=True,
)
print("✅ Sintaxe válida")

print("\n=== PYTEST ===")
subprocess.run(
    [str(PYTHON), "-m", "pytest", "-q"],
    cwd=ROOT / "backend",
    check=True,
)

print("\n" + "=" * 72)
print("✅ PATCH INSTALADO")
print(f"Backup: {BACKUP}")
print("Esperado após reiniciar:")
print("- Redes CIDR → modelo deterministic-ipv4-cidr-v1 / hybrid-v9")
print("- Requisitórios e rótulos (D) → rejeitados")
print("=" * 72)
