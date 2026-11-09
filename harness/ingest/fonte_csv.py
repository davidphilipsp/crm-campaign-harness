"""Adapter FonteZ0 sobre o export CSV do Smartico (E2, CRM.md).

Envolve `le_csv` sem mudar seu comportamento -- prova que a porta `FonteZ0`
cabe na fonte que ja funciona antes de aceitar uma fonte nova.
"""

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from harness.ingest.reader import le_csv


@dataclass(frozen=True)
class FonteCSV:
    caminho: Path
    colunas_esperadas: tuple[str, ...] | None = None

    def linhas(self) -> Iterator[dict[str, str]]:
        return le_csv(self.caminho, colunas_esperadas=self.colunas_esperadas)

    def proveniencia(self) -> dict[str, str]:
        return {
            "fonte": "csv",
            "caminho": str(self.caminho),
            "sha256": _sha256_arquivo(self.caminho),
        }


def _sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()
