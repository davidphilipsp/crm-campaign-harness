from decimal import Decimal

import pytest

from harness.digest import canonico, digest_hash


def test_ordem_de_chave_nao_muda_hash() -> None:
    a = {"taxa": Decimal("0.61"), "braco": "controle"}
    b = {"braco": "controle", "taxa": Decimal("0.61")}
    assert digest_hash(a) == digest_hash(b)


def test_escala_diferente_muda_hash() -> None:
    assert digest_hash({"t": Decimal("0.61")}) != digest_hash({"t": Decimal("0.610")})


def test_quantizacao_reconcilia() -> None:
    q = Decimal("0.0001")
    a = Decimal("0.61").quantize(q)
    b = Decimal("0.610").quantize(q)
    assert digest_hash({"t": a}) == digest_hash({"t": b})


def test_sem_espaco_em_branco() -> None:
    assert b" " not in canonico({"a": 1, "b": 2})


def test_float_e_recusado() -> None:
    with pytest.raises(TypeError):
        canonico({"t": {1.5}})
