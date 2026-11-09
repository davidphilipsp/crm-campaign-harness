"""Registry de risk squads consumidores (E23).

Mesmo raciocinio de harness/casas.py (B0.3): terceiro squad e uma linha em
config/squads.yaml, zero linha de codigo.
"""

from functools import lru_cache
from pathlib import Path

from harness.tools import carrega

_CAMINHO = Path(__file__).resolve().parent.parent / "config" / "squads.yaml"


@lru_cache(maxsize=1)
def squads_validos() -> frozenset[str]:
    itens = carrega(_CAMINHO, cabecalho="squads:")
    return frozenset(item["nome"] for item in itens)
