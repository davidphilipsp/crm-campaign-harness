"""Unica fronteira com o driver psycopg (E2/E3, A3, CRM.md).

Nucleo do harness fica em stdlib puro (`dependencies = []`, pyproject.toml).
psycopg entra so como `[project.optional-dependencies]` e so e importado
aqui, em runtime, depois de confirmar que esta instalado -- mesmo padrao de
deteccao que `compute/_engine.py` usaria para pandas (find_spec, erro
nomeado, nunca degradacao silenciosa).
"""

import importlib.util
import os
from collections.abc import Iterator, Mapping
from typing import Any


class DriverAusente(Exception):
    def __init__(self) -> None:
        super().__init__("driver postgres ausente: pip install 'crm-harness[postgres]'")


class CredencialAusente(Exception):
    def __init__(self, variavel: str) -> None:
        super().__init__(f"credencial ausente: defina {variavel}")


def exige_psycopg() -> None:
    if importlib.util.find_spec("psycopg") is None:
        raise DriverAusente


def dsn_da_casa(casa: str) -> str:
    """`HARNESS_PG_DSN_<CASA>`, sem fallback. Ausente estoura, nunca default."""
    variavel = f"HARNESS_PG_DSN_{casa.upper()}"
    dsn = os.environ.get(variavel)
    if not dsn:
        raise CredencialAusente(variavel)
    return dsn


def executa(dsn: str, sql: str, params: Mapping[str, str]) -> Iterator[dict[str, Any]]:
    """Roda uma unica query em transacao read-only.

    Params sempre por binding do driver -- nunca interpolacao de string.
    Credenciais so via env (`HARNESS_PG_DSN_<CASA>`, E21, CRM.md); nunca
    no repositorio.
    """
    exige_psycopg()
    import psycopg  # import tardio: so alcancavel depois do guard acima

    with psycopg.connect(dsn) as conn:
        conn.execute("set transaction read only")
        with conn.cursor() as cur:
            cur.execute(sql, params)
            colunas = [d.name for d in cur.description or ()]
            for linha in cur:
                yield dict(zip(colunas, linha, strict=True))
