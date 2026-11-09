from collections.abc import Iterable
from pathlib import PurePosixPath

EXTENSOES_DE_DADO = frozenset({".csv", ".tsv", ".xlsx", ".xls", ".parquet", ".jsonl"})
PREFIXO_PERMITIDO = "tests/"


class ArquivoProibido(Exception):
    """Commit recusado: arquivo de dado fora de tests/ (§3.6)."""

    def __init__(self, caminhos: tuple[str, ...]) -> None:
        self.caminhos = caminhos
        lista = "\n  ".join(caminhos)
        super().__init__(
            f"commit recusado: {len(caminhos)} arquivo(s) de dado fora de "
            f"{PREFIXO_PERMITIDO}\n  {lista}"
        )


def _proibido(caminho: str) -> bool:
    p = PurePosixPath(caminho)
    if p.suffix.lower() not in EXTENSOES_DE_DADO:
        return False
    return not caminho.startswith(PREFIXO_PERMITIDO)


def checa_staged(caminhos: Iterable[str]) -> None:
    """Levanta ArquivoProibido citando todos os ofensores de uma vez."""
    ofensores = tuple(c for c in caminhos if _proibido(c))
    if ofensores:
        raise ArquivoProibido(ofensores)
