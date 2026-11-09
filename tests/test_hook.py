import pytest

from harness.hooks import ArquivoProibido, checa_staged

PROIBIDOS = [
    "data/online-ontem.csv",
    "qualquer/lugar/export.csv",
    "tests_fora/x.csv",
    "data/dump.xlsx",
]
PERMITIDOS = [
    "tests/fixtures/pii_email.csv",
    "tests/golden/reativacao_sabado/entrada.csv",
    "harness/reader.py",
    "CRM.md",
]


@pytest.mark.parametrize("caminho", PROIBIDOS)
def test_recusa(caminho: str) -> None:
    with pytest.raises(ArquivoProibido):
        checa_staged([caminho])


def test_permite_lote_limpo() -> None:
    checa_staged(PERMITIDOS)


def test_recusa_lote_misto_e_cita_todos() -> None:
    with pytest.raises(ArquivoProibido) as exc:
        checa_staged([*PERMITIDOS, "data/a.csv", "data/b.csv"])
    assert "data/a.csv" in str(exc.value)
    assert "data/b.csv" in str(exc.value)
