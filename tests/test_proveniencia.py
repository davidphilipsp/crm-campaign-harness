"""Fecha A4: proveniencia e campo hasheado do Digest, nao decorativo.

A1 deu o campo a Digest; A3 deu a FontePostgres a forma correta
(fonte/casa/query/sha256). Este modulo prova a costura completa: dois
digests identicos em tudo, exceto o sha256 da query de origem, produzem
hash diferente -- e que a forma de proveniencia de uma fonte Postgres
chega inteira ao digest arquivado.
"""

from decimal import Decimal

import pytest

from harness.contracts import Braco, Digest, EtapaFunil, Numero
from harness.digest import digest_hash
from harness.ingest.agrega import monta_digest
from harness.ingest.catalogo import carrega_por_nome
from tests.fixtures.fonte_fake import FonteFake

INI, FIM = "2026-07-01T00:00:00Z", "2026-07-08T00:00:00Z"


def _digest_com_proveniencia(prov: dict[str, str]) -> Digest:
    e = EtapaFunil("enviado", Numero(Decimal("100"), "medido"))
    return Digest(
        casa="brand_a", fase="leitura", universo="csv", campanha_id="x",
        janela_inicio=INI, janela_fim=FIM, hipotese="h", contexto="",
        bracos=(Braco("tratamento", (e,)),),
        proveniencia=prov,
    )


def test_sha256_diferente_na_proveniencia_muda_o_hash_do_digest() -> None:
    base = {"fonte": "postgres", "query": "executive_kpis"}
    a = _digest_com_proveniencia({**base, "sha256": "a" * 64})
    b = _digest_com_proveniencia({**base, "sha256": "b" * 64})
    assert digest_hash(a.como_dict()) != digest_hash(b.como_dict())


def test_proveniencia_exige_fonte() -> None:
    with pytest.raises(ValueError, match="proveniencia"):
        _digest_com_proveniencia({})


def test_proveniencia_de_query_chega_inteira_ao_digest_arquivado() -> None:
    """Nome + sha256 da query (E3) sobrevivem ate o digest final, sem banco."""
    q = carrega_por_nome("player_risk_signals")
    fonte = FonteFake(
        dados=({"user_ext_id": "u1", "fact_type_id": "2", "communication_id": "c1"},),
        _proveniencia={"fonte": "postgres", "casa": "brand_a", "query": q.nome, "sha256": q.sha256},
    )
    d = monta_digest(
        fonte, braco="tratamento", casa="brand_a", universo="state", campanha_id="9000001",
        janela_inicio=INI, janela_fim=FIM,
        hipotese="oferta converte mais que a generica", contexto="",
    )
    assert d.proveniencia == {
        "fonte": "postgres", "casa": "brand_a", "query": "player_risk_signals", "sha256": q.sha256,
    }
    # arquivado: aparece no dict hasheado, nao so no objeto em memoria
    assert "player_risk_signals" in str(d.como_dict())
