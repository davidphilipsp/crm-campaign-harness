from decimal import Decimal
from pathlib import Path

import pytest

from harness.pisos import carrega_piso


def test_default_quando_crm_md_nao_tem_valor(tmp_path: Path) -> None:
    crm = tmp_path / "CRM.md"
    crm.write_text("## 6 · Constantes de negocio\n\n<!-- vazio -->\n", encoding="utf-8")
    p = carrega_piso("C3_ENTREGA_MINIMA", caminho_crm_md=crm)
    assert p.valor == Decimal("0.85")
    assert p.origem == "default_nao_validado"


def test_default_quando_crm_md_nao_existe(tmp_path: Path) -> None:
    p = carrega_piso("C2_DESVIO_MAX_BRACOS", caminho_crm_md=tmp_path / "nao_existe.md")
    assert p.valor == Decimal("0.05")
    assert p.origem == "default_nao_validado"


def test_crm_md_vence_o_default(tmp_path: Path) -> None:
    crm = tmp_path / "CRM.md"
    crm.write_text(
        "## 6 · Constantes de negocio\n\n"
        "| constante | valor |\n|---|---|\n"
        "| C3_ENTREGA_MINIMA | 0.90 |\n",
        encoding="utf-8",
    )
    p = carrega_piso("C3_ENTREGA_MINIMA", caminho_crm_md=crm)
    assert p.valor == Decimal("0.90")
    assert p.origem == "crm_md"


def test_valor_fora_da_secao_6_e_ignorado(tmp_path: Path) -> None:
    crm = tmp_path / "CRM.md"
    crm.write_text(
        "## 5 · outra secao\n\n| C3_ENTREGA_MINIMA | 0.99 |\n\n"
        "## 6 · Constantes de negocio\n\n<!-- vazio -->\n",
        encoding="utf-8",
    )
    p = carrega_piso("C3_ENTREGA_MINIMA", caminho_crm_md=crm)
    assert p.origem == "default_nao_validado"


def test_piso_desconhecido_estoura() -> None:
    with pytest.raises(ValueError):
        carrega_piso("C99_NAO_EXISTE")


def test_todos_os_defaults_documentados_no_prompt() -> None:
    assert carrega_piso("C_AMOSTRA_MIN_CONTRASTE").valor == Decimal("30")
    assert carrega_piso("CTOR_MAX_ANOMALO").valor == Decimal("0.60")
    assert carrega_piso("COBERTURA_MIN_DADO").valor == Decimal("0.90")


def test_crm_md_real_do_repo_tem_cobertura_min_dado_decidida() -> None:
    """E25: CRM.md §6 (arquivo real do repo, nao fixture) tem
    COBERTURA_MIN_DADO carimbado a partir do relatorio de torneios da
    brand-a -- os outros tres pisos seguem default_nao_validado porque
    nenhuma analise real disponivel toca o funil SMS que eles avaliam."""
    p_cobertura = carrega_piso("COBERTURA_MIN_DADO")
    assert p_cobertura.valor == Decimal("0.90")
    assert p_cobertura.origem == "crm_md"

    for nome in ("C3_ENTREGA_MINIMA", "C2_DESVIO_MAX_BRACOS", "CTOR_MAX_ANOMALO"):
        assert carrega_piso(nome).origem == "default_nao_validado", nome
