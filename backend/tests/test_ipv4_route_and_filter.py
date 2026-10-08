from haila.contracts import NucleoQuestao
from haila.hybrid import gerar_distratores_ipv4_cidr
from haila.generator import _motivo_candidato_pos_filtro

def _nucleo(gabarito):
    return NucleoQuestao(
        "Em uma rede IPv4, escolha o prefixo CIDR adequado para 30 hosts.",
        gabarito,
        "Explicação suficiente para o teste.",
        "Redes",
        "Aplicar subnetting",
        "IPv4 e CIDR",
    )

def test_ipv4_prefixo_curto():
    ds = gerar_distratores_ipv4_cidr("/27", "Rede IPv4 para 30 hosts")
    assert ds is not None and len(ds) == 4
    assert "/27" not in [d.texto for d in ds]
    assert len({d.texto for d in ds}) == 4

def test_ipv4_mascara_decimal():
    ds = gerar_distratores_ipv4_cidr(
        "Máscara /28 (255.255.255.240)",
        "Subnetting IPv4",
    )
    assert ds is not None and len(ds) == 4
    assert all("Máscara /" in d.texto for d in ds)

def test_plural_regular_nao_e_corrupcao():
    n = _nucleo("Requisito não funcional")
    assert _motivo_candidato_pos_filtro(n, "Requisitos funcionais") is None

def test_requisitorios_e_rejeitado():
    n = _nucleo("Requisito não funcional")
    assert _motivo_candidato_pos_filtro(n, "Requisitórios") is not None

def test_rotulo_embutido_e_rejeitado():
    n = _nucleo("Requisito não funcional")
    assert _motivo_candidato_pos_filtro(n, "(D) Definição de projeto") is not None
