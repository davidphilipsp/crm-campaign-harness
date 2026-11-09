from pathlib import Path

import pytest

from harness.docs import FIM, INICIO, gera, tabela

RAIZ = Path(__file__).resolve().parent.parent


def test_skill_md_esta_em_dia() -> None:
    esperado = tabela(RAIZ / "tools.yaml")
    atual = (RAIZ / "SKILL.md").read_text(encoding="utf-8")
    miolo = atual[atual.index(INICIO) + len(INICIO) : atual.index(FIM)].strip()
    assert miolo == esperado, "SKILL.md desatualizado: rode o gerador"


def test_gera_recusa_md_sem_marcador(tmp_path: Path) -> None:
    md = tmp_path / "x.md"
    md.write_text("sem marcador\n", encoding="utf-8", newline="\n")
    with pytest.raises(ValueError):
        gera(RAIZ / "tools.yaml", md)


def test_gera_e_idempotente(tmp_path: Path) -> None:
    md = tmp_path / "x.md"
    md.write_text(f"topo\n{INICIO}\n{FIM}\nrodape\n", encoding="utf-8", newline="\n")
    gera(RAIZ / "tools.yaml", md)
    uma = md.read_text(encoding="utf-8")
    gera(RAIZ / "tools.yaml", md)
    assert md.read_text(encoding="utf-8") == uma
