import pytest

from harness.ingest.catalogo import QueryNomeada, carrega_por_nome
from harness.ingest.fonte import FonteZ0
from harness.ingest.pg import FontePostgres
from harness.ingest.pg._driver import DriverAusente


def _query() -> QueryNomeada:
    return carrega_por_nome("executive_kpis")


def test_fonte_postgres_satisfaz_o_protocolo() -> None:
    fonte = FontePostgres(
        casa="brand_a",
        query=_query(),
        params={"janela_inicio": "2026-01-01", "janela_fim": "2026-01-31"},
    )
    assert isinstance(fonte, FonteZ0)


def test_fonte_postgres_proveniencia_identifica_query_sem_conectar() -> None:
    q = _query()
    fonte = FontePostgres(
        casa="brand_a",
        query=q,
        params={"janela_inicio": "2026-01-01", "janela_fim": "2026-01-31"},
    )
    assert fonte.proveniencia() == {
        "fonte": "postgres",
        "casa": "brand_a",
        "query": "executive_kpis",
        "sha256": q.sha256,
    }


def test_fonte_postgres_recusa_sem_driver_antes_de_qualquer_coisa() -> None:
    """Sem psycopg instalado, linhas() estoura antes de tocar DSN ou rede."""
    fonte = FontePostgres(casa="brand_a", query=_query(), params={})
    with pytest.raises(DriverAusente):
        list(fonte.linhas())
