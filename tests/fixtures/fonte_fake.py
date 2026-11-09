"""FonteZ0 em memoria: prova o pipeline sem arquivo nem banco (A1, A3)."""

from collections.abc import Iterator
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FonteFake:
    dados: tuple[dict[str, str], ...]
    _proveniencia: dict[str, str] = field(default_factory=lambda: {"fonte": "fake"})

    def linhas(self) -> Iterator[dict[str, str]]:
        return iter(self.dados)

    def proveniencia(self) -> dict[str, str]:
        return self._proveniencia
