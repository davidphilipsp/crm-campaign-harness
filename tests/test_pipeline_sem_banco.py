"""Prova que monta_digest roda de ponta a ponta com uma fonte no formato
Postgres (proveniencia de query, nao de arquivo), sem tocar driver nem rede
(A3). FonteFake substitui FontePostgres inteiramente."""

from harness.ingest.agrega import monta_digest
from tests.fixtures.fonte_fake import FonteFake

BASE = {
    "casa": "brand_a",
    "campanha_id": "9000001",
    "janela_inicio": "2026-07-01T00:00:00Z",
    "janela_fim": "2026-07-08T00:00:00Z",
    "hipotese": "oferta converte mais que generica",
    "contexto": "",
}


def test_pipeline_aceita_fonte_com_proveniencia_de_query() -> None:
    fonte = FonteFake(
        dados=({"user_ext_id": "u1", "fact_type_id": "2", "communication_id": "c1"},),
        _proveniencia={
            "fonte": "postgres",
            "casa": "brand_a",
            "query": "executive_kpis",
            "sha256": "a" * 64,
        },
    )
    d = monta_digest(fonte, braco="tratamento", universo="state", **BASE)
    assert d.proveniencia["fonte"] == "postgres"
    assert d.proveniencia["query"] == "executive_kpis"
