"""Porta Z0: contrato estrutural para qualquer origem de linha bruta.

Lint, calculo, laco e ledger consomem Digest, nao linha -- por isso uma fonte
nova custa um adapter aqui e zero mudanca downstream (E2/E3, CRM.md).
"""

from collections.abc import Iterator
from typing import Protocol, runtime_checkable


@runtime_checkable
class FonteZ0(Protocol):
    """Qualquer origem de linha bruta. Contrato do lado Z0 da fronteira."""

    def linhas(self) -> Iterator[dict[str, str]]: ...

    def proveniencia(self) -> dict[str, str]:
        """O que reconstroi a decisao depois: arquivo ou query, versao, hash."""
        ...
