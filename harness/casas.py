"""Registry de casas operacionais (E1, B0.3).

`Casa` deixou de ser Literal fechado em contracts.py: adicionar uma casa e
uma linha em config/casas.yaml, zero linha de codigo.
"""

from functools import lru_cache
from pathlib import Path

from harness.tools import carrega

_CAMINHO = Path(__file__).resolve().parent.parent / "config" / "casas.yaml"


@lru_cache(maxsize=1)
def casas_validas() -> frozenset[str]:
    itens = carrega(_CAMINHO, cabecalho="casas:")
    return frozenset(item["nome"] for item in itens)
