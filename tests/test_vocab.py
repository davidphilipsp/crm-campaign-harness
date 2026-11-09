import pytest

from harness.ingest.vocab import ORDEM_FUNIL, etapa_de_fact_type


def test_traduz_fact_types_conhecidos() -> None:
    assert etapa_de_fact_type(2) == "enviado"
    assert etapa_de_fact_type(6) == "entregue"
    assert etapa_de_fact_type(4) == "clicado"


def test_impression_e_read_mapeiam_para_aberto() -> None:
    assert etapa_de_fact_type(3) == "aberto"
    assert etapa_de_fact_type(8) == "aberto"


@pytest.mark.parametrize("codigo", [1, 5, 7, 9, 10])
def test_fact_types_fora_do_funil_retornam_none(codigo: int) -> None:
    assert etapa_de_fact_type(codigo) is None


def test_codigo_desconhecido_estoura() -> None:
    with pytest.raises(ValueError):
        etapa_de_fact_type(99)


def test_ordem_do_funil_nao_e_ordem_numerica() -> None:
    codigos = [2, 6, 3, 4]
    assert [etapa_de_fact_type(c) for c in codigos] == list(ORDEM_FUNIL)
    assert codigos != sorted(codigos)
