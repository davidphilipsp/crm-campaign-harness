import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from harness.persist.resultados import (
    eh_preflight,
    grava_preflight,
    le_c8,
    le_spec,
    le_veredicto_preflight,
)
from harness.pisos import Piso
from harness.preflight import (
    SpecCampanha,
    avalia_duracao_vs_delays,
    avalia_fonte_conversao_controle,
    avalia_mde_vs_base,
)
from harness.publica.documento import c8_dict, veredicto_preflight_dict


def _spec() -> SpecCampanha:
    return SpecCampanha(
        fase="preflight", casa="brand_a", universo="csv", regua="reativacao-30d",
        base_estimada=150000, pct_holdout=Decimal("0.05"),
        conversao_esperada=Decimal("0.03"), fonte_conversao_controle="evento_atribuido",
        max_duration_s=86400, delays_s=(3600, 7200),
    )


def test_grava_preflight_no_caminho_esperado(tmp_path: Path) -> None:
    spec = _spec()
    agora = datetime(2026, 8, 1, 12, tzinfo=UTC)
    caminho = grava_preflight(spec, saida=tmp_path, agora=agora)
    assert caminho == tmp_path / "brand_a" / "reativacao-30d" / "20260801T120000.000000Z.json"
    assert caminho.exists()


def test_grava_preflight_fase_e_preflight(tmp_path: Path) -> None:
    caminho = grava_preflight(_spec(), saida=tmp_path)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados["spec"]["fase"] == "preflight"
    assert eh_preflight(dados)


def test_grava_preflight_nunca_sobrescreve(tmp_path: Path) -> None:
    spec = _spec()
    agora = datetime(2026, 8, 1, tzinfo=UTC)
    grava_preflight(spec, saida=tmp_path, agora=agora)
    with pytest.raises(FileExistsError):
        grava_preflight(spec, saida=tmp_path, agora=agora)


def test_le_spec_reconstroi_o_que_grava_preflight_escreveu(tmp_path: Path) -> None:
    original = _spec()
    caminho = grava_preflight(original, saida=tmp_path)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert le_spec(dados["spec"]) == original


def test_grava_preflight_c8_c9_c11_batem_com_documento_dict(tmp_path: Path) -> None:
    spec = _spec()
    piso_amostra = Piso(Decimal("30"), "default_nao_validado")
    piso_mde_ok = Piso(Decimal("0.25"), "cli")
    c8 = avalia_mde_vs_base(spec, piso_amostra=piso_amostra, piso_mde_ok=piso_mde_ok)
    c9 = avalia_fonte_conversao_controle(spec)
    c11 = avalia_duracao_vs_delays(spec)

    caminho = grava_preflight(spec, saida=tmp_path, c8=c8, c9=c9, c11=c11)
    dados = json.loads(caminho.read_text(encoding="utf-8"))

    assert dados["c8"] == c8_dict(c8)
    assert dados["c9"] == veredicto_preflight_dict(c9)
    assert dados["c11"] == veredicto_preflight_dict(c11)
    assert dados["c8"]["piso_mde_ok"]["origem"] == "cli"


def test_le_c8_e_le_veredicto_preflight_reconstroem(tmp_path: Path) -> None:
    spec = _spec()
    piso_amostra = Piso(Decimal("30"), "default_nao_validado")
    piso_mde_ok = Piso(Decimal("0.25"), "cli")
    c8 = avalia_mde_vs_base(spec, piso_amostra=piso_amostra, piso_mde_ok=piso_mde_ok)
    c9 = avalia_fonte_conversao_controle(spec)

    caminho = grava_preflight(spec, saida=tmp_path, c8=c8, c9=c9)
    dados = json.loads(caminho.read_text(encoding="utf-8"))

    assert le_c8(dados["c8"]) == c8
    assert le_veredicto_preflight(dados["c9"]) == c9


def test_eh_preflight_distingue_dos_dois_envelopes() -> None:
    assert eh_preflight({"spec": {}})
    assert not eh_preflight({"digest": {}})
