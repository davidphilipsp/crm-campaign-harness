from decimal import Decimal
from typing import Any

import pytest

from harness.pisos import Piso
from harness.preflight import (
    SpecCampanha,
    avalia_duracao_vs_delays,
    avalia_fonte_conversao_controle,
    avalia_mde_vs_base,
)

BASE: dict[str, Any] = {
    "fase": "preflight",
    "casa": "brand_a",
    "universo": "csv",
    "regua": "anti-churn",
    "base_estimada": 3000,
    "pct_holdout": Decimal("0.05"),
    "conversao_esperada": Decimal("0.10"),
    "fonte_conversao_controle": "evento_atribuido",
    "max_duration_s": 3600,
    "delays_s": (600, 600),
}


def _spec(**overrides: Any) -> SpecCampanha:
    return SpecCampanha(**{**BASE, **overrides})


# --- SpecCampanha invariantes ---------------------------------------------


def test_spec_valida_aceita() -> None:
    s = _spec()
    assert s.casa == "brand_a"


def test_spec_recusa_fase_leitura() -> None:
    with pytest.raises(ValueError):
        _spec(fase="leitura")


def test_spec_recusa_casa_desconhecida() -> None:
    with pytest.raises(ValueError):
        _spec(casa="cassino_inexistente")


def test_spec_recusa_pct_holdout_fora_do_intervalo() -> None:
    with pytest.raises(ValueError):
        _spec(pct_holdout=Decimal("1"))


def test_spec_recusa_delay_negativo() -> None:
    with pytest.raises(ValueError):
        _spec(delays_s=(-1,))


# --- C8: MDE vs base --------------------------------------------------------

PISO_AMOSTRA = Piso(Decimal("30"), "default_nao_validado")
PISO_MDE_OK = Piso(Decimal("0.20"), "default_nao_validado")


def test_c8_base_pequena_e_ilegivel() -> None:
    # 3k base, 5% holdout -> ~150 controles, conversao 10% -> ~15 eventos esperados
    r = avalia_mde_vs_base(_spec(), piso_amostra=PISO_AMOSTRA, piso_mde_ok=PISO_MDE_OK)
    assert r.n_holdout == 150
    assert r.veredito == "ILEGIVEL"
    assert r.alternativas == (
        "pooling entre ciclos da mesma regua",
        "declarar comparativo desde o inicio",
    )


def test_c8_base_grande_e_ok() -> None:
    r = avalia_mde_vs_base(
        _spec(base_estimada=2_000_000, pct_holdout=Decimal("0.50")),
        piso_amostra=PISO_AMOSTRA,
        piso_mde_ok=PISO_MDE_OK,
    )
    assert r.veredito == "OK"
    assert r.alternativas == ()


def test_c8_base_intermediaria_e_limitrofe() -> None:
    # amostra suficiente para nao ser ILEGIVEL (eventos_min >= 30), mas MDE
    # relativo acima do piso_mde_ok -> LIMITROFE, nao OK.
    r = avalia_mde_vs_base(
        _spec(base_estimada=3_000, pct_holdout=Decimal("0.50")),
        piso_amostra=PISO_AMOSTRA,
        piso_mde_ok=PISO_MDE_OK,
    )
    assert r.veredito == "LIMITROFE"


def test_c8_mais_amostra_reduz_o_mde() -> None:
    pequeno = avalia_mde_vs_base(
        _spec(base_estimada=10_000), piso_amostra=PISO_AMOSTRA, piso_mde_ok=PISO_MDE_OK
    )
    grande = avalia_mde_vs_base(
        _spec(base_estimada=1_000_000), piso_amostra=PISO_AMOSTRA, piso_mde_ok=PISO_MDE_OK
    )
    assert grande.mde_relativo < pequeno.mde_relativo


def test_c8_nao_hardcoda_z_alterando_poder_muda_resultado() -> None:
    # mesmo n e conversao, pisos diferentes -> mesmo mde, mas prova que o
    # calculo depende de NormalDist (nao de uma constante fixa): mde escala
    # com sqrt(1/n1 + 1/n2), nao e uma razao fixa entre os casos.
    r1 = avalia_mde_vs_base(
        _spec(base_estimada=4_000), piso_amostra=PISO_AMOSTRA, piso_mde_ok=PISO_MDE_OK
    )
    r2 = avalia_mde_vs_base(
        _spec(base_estimada=16_000), piso_amostra=PISO_AMOSTRA, piso_mde_ok=PISO_MDE_OK
    )
    razao = r1.mde_absoluto / r2.mde_absoluto
    assert Decimal("1.9") < razao < Decimal("2.1")  # sqrt(4x amostra) = 2x


# --- C9: fonte de conversao do controle ------------------------------------


def test_c9_no_flow_reprova() -> None:
    v = avalia_fonte_conversao_controle(_spec(fonte_conversao_controle="no_flow"))
    assert v.check == "C9"
    assert v.aprova is False


@pytest.mark.parametrize("fonte", ["evento_atribuido", "ausente"])
def test_c9_outras_fontes_aprovam(fonte: str) -> None:
    v = avalia_fonte_conversao_controle(_spec(fonte_conversao_controle=fonte))
    assert v.aprova is True


# --- C11: duracao vs delays --------------------------------------------------


def test_c11_duracao_menor_que_delays_reprova() -> None:
    v = avalia_duracao_vs_delays(_spec(max_duration_s=100, delays_s=(60, 60)))
    assert v.check == "C11"
    assert v.aprova is False


def test_c11_duracao_suficiente_aprova() -> None:
    v = avalia_duracao_vs_delays(_spec(max_duration_s=120, delays_s=(60, 60)))
    assert v.aprova is True


def test_c11_caso_real_1_dia_vs_38h_mais_delays() -> None:
    # caso real citado no prompt: Max duration = 1 Day vs 19h + 19h + delays
    v = avalia_duracao_vs_delays(
        _spec(max_duration_s=86_400, delays_s=(19 * 3600, 19 * 3600, 2 * 3600))
    )
    assert v.aprova is False
