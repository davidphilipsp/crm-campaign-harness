"""Adapter FonteZ0 sobre a replica Postgres de uma casa (E2, CRM.md).

Credenciais so via env (`HARNESS_PG_DSN_<CASA>`, E21, CRM.md). Nenhum teste da suite conecta a banco -- ver
tests/test_fonte_postgres.py e tests/fixtures/fonte_fake.py para a prova
do pipeline sem rede.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass

from harness.ingest.catalogo import QueryNomeada
from harness.ingest.pg._driver import dsn_da_casa, executa, exige_psycopg


@dataclass(frozen=True)
class FontePostgres:
    casa: str
    query: QueryNomeada
    params: Mapping[str, str]

    def linhas(self) -> Iterator[dict[str, str]]:
        exige_psycopg()
        dsn = dsn_da_casa(self.casa)
        for linha in executa(dsn, self.query.sql, self.params):
            yield {chave: "" if valor is None else str(valor) for chave, valor in linha.items()}

    def proveniencia(self) -> dict[str, str]:
        return {
            "fonte": "postgres",
            "casa": self.casa,
            "query": self.query.nome,
            "sha256": self.query.sha256,
        }
