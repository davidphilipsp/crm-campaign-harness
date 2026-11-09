"""Mesmo contrato de harness.docs -> SKILL.md (tests/test_docs.py): roda o
gerador puro e compara a saida, byte a byte, contra o arquivo commitado --
sem escrever nada em disco. Divergencia quebra a suite: fixture golden
desalinhada do gerador que a produz e pior que sem gerador nenhum."""

from pathlib import Path

from tools.gera_golden import _formata_csv, _gera_latencia_impossivel, _gera_demo_9000001

RAIZ = Path(__file__).resolve().parent.parent


def test_demo_9000001_bate_byte_a_byte_com_o_gerador() -> None:
    esperado = _formata_csv(_gera_demo_9000001())
    atual = (RAIZ / "tests" / "golden" / "demo_9000001" / "entrada.csv").read_text(
        encoding="utf-8"
    )
    assert atual == esperado, "entrada.csv desalinhado com tools/gera_golden.py -- rode o gerador"


def test_latencia_impossivel_bate_byte_a_byte_com_o_gerador() -> None:
    esperado = _formata_csv(_gera_latencia_impossivel())
    atual = (RAIZ / "tests" / "golden" / "latencia_impossivel" / "entrada.csv").read_text(
        encoding="utf-8"
    )
    assert atual == esperado, "entrada.csv desalinhado com tools/gera_golden.py -- rode o gerador"
