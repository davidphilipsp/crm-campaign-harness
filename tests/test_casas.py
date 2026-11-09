from decimal import Decimal

import pytest

from harness.casas import casas_validas
from harness.contracts import Braco, Digest, EtapaFunil, Numero

INI = "2026-07-01T00:00:00Z"
FIM = "2026-07-08T00:00:00Z"


def _braco() -> Braco:
    e = EtapaFunil("enviado", Numero(Decimal("1000"), "medido"))
    return Braco("tratamento", (e,))


def test_registry_tem_as_duas_casas_conhecidas() -> None:
    assert casas_validas() == frozenset({"brand_a", "brand_b"})


def test_digest_aceita_casa_do_registry() -> None:
    d = Digest(
        casa="brand_a",
        fase="leitura",
        universo="csv",
        campanha_id="C-42",
        janela_inicio=INI,
        janela_fim=FIM,
        hipotese="oferta converte mais que generica",
        contexto="",
        bracos=(_braco(),),
        proveniencia={"fonte": "teste"},
    )
    assert d.casa == "brand_a"


def test_digest_recusa_casa_fora_do_registry() -> None:
    with pytest.raises(ValueError):
        Digest(
            casa="cassino_inexistente",
            fase="leitura",
            universo="csv",
            campanha_id="C-42",
            janela_inicio=INI,
            janela_fim=FIM,
            hipotese="oferta converte mais que generica",
            contexto="",
            bracos=(_braco(),),
            proveniencia={"fonte": "teste"},
        )
