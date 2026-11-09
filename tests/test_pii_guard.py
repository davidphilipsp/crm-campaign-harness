import pytest

from harness.ingest.pii_guard import cpf_valido, tem_email


@pytest.mark.parametrize("valor", ["111.444.777-35", "11144477735"])
def test_aceita_cpf_valido(valor: str) -> None:
    assert cpf_valido(valor) is True


@pytest.mark.parametrize(
    "valor",
    ["111.444.777-36", "11111111111", "00000000000", "123", "111444777351", "abc", ""],
)
def test_recusa(valor: str) -> None:
    assert cpf_valido(valor) is False


@pytest.mark.parametrize(
    "valor",
    [
        "joao@brand-a.example",
        "contato: ana@brand-b.example urgente",
        "JOAO.SILVA+tag@sub.dominio.com.br",
    ],
)
def test_detecta_email(valor: str) -> None:
    assert tem_email(valor) is True


@pytest.mark.parametrize(
    "valor",
    ["sem email aqui", "a@b", "@brand-a.example", "joao@", "", "12345678901"],
)
def test_nao_detecta_email(valor: str) -> None:
    assert tem_email(valor) is False
