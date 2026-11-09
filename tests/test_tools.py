from pathlib import Path

import pytest

from harness.tools import carrega

OK = "tools:\n  - nome: ingest\n    zona: Z0->Z1\n"


def _escreve(tmp_path: Path, texto: str) -> Path:
    p = tmp_path / "t.yaml"
    p.write_text(texto, encoding="utf-8", newline="\n")
    return p


def test_carrega_item(tmp_path: Path) -> None:
    (t,) = carrega(_escreve(tmp_path, OK))
    assert t == {"nome": "ingest", "zona": "Z0->Z1"}


@pytest.mark.parametrize(
    "texto",
    [
        "outra_coisa:\n",
        "tools:\n    zona: Z1\n",
        "tools:\n  - nome: x\n      extra: y\n",
        "tools:\n  - nome\n",
        "tools:\n  nome: x\n",
    ],
)
def test_recusa_forma_invalida(tmp_path: Path, texto: str) -> None:
    with pytest.raises(ValueError):
        carrega(_escreve(tmp_path, texto))
