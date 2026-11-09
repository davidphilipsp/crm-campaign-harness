from decimal import Decimal
from typing import Any

import pytest

from harness.contracts import ORDEM_BUCKETS_LATENCIA, Numero
from harness.ingest.agrega import monta_digest
from tests.fixtures.fonte_fake import FonteFake

BASE: dict[str, Any] = {
    "casa": "brand_a",
    "campanha_id": "9000001",
    "janela_inicio": "2026-07-01T00:00:00Z",
    "janela_fim": "2026-07-08T00:00:00Z",
    "hipotese": "oferta converte mais que generica",
    "contexto": "",
}


def _linha(uid: str, ft: str, cid: str, event_time: str = "") -> dict[str, str]:
    linha = {"user_ext_id": uid, "fact_type_id": ft, "communication_id": cid}
    if event_time:
        linha["event_time"] = event_time
    return linha


def _fonte(*linhas: dict[str, str]) -> FonteFake:
    return FonteFake(tuple(linhas))


def test_conta_usuarios_distintos_nao_eventos() -> None:
    fonte = _fonte(_linha("1", "2", "c1"), _linha("1", "2", "c2"), _linha("2", "2", "c3"))
    d = monta_digest(fonte, braco="tratamento", universo="csv", **BASE)
    (etapa,) = d.bracos[0].etapas
    assert etapa.nome == "enviado"
    assert str(etapa.volume.valor) == "2"


def test_deduplica_communication_id_repetido() -> None:
    fonte = _fonte(_linha("1", "2", "c1"), _linha("1", "2", "c1"))
    d = monta_digest(fonte, braco="tratamento", universo="csv", **BASE)
    assert str(d.bracos[0].etapas[0].volume.valor) == "1"


def test_ignora_fact_type_fora_do_funil() -> None:
    fonte = _fonte(_linha("1", "2", "c1"), _linha("1", "5", "c2"), _linha("1", "7", "c3"))
    d = monta_digest(fonte, braco="tratamento", universo="csv", **BASE)
    assert [e.nome for e in d.bracos[0].etapas] == ["enviado"]


def test_etapas_saem_na_ordem_do_funil() -> None:
    fonte = _fonte(_linha("1", "4", "a"), _linha("1", "2", "b"), _linha("1", "6", "c"))
    d = monta_digest(fonte, braco="tratamento", universo="csv", **BASE)
    assert [e.nome for e in d.bracos[0].etapas] == ["enviado", "entregue", "clicado"]


def test_etapa_sem_evento_nao_vira_zero() -> None:
    fonte = _fonte(_linha("1", "2", "c1"))
    d = monta_digest(fonte, braco="tratamento", universo="csv", **BASE)
    assert all(e.volume.rotulo == "medido" for e in d.bracos[0].etapas)
    assert "aberto" not in [e.nome for e in d.bracos[0].etapas]


def test_sem_linha_nenhuma_estoura() -> None:
    with pytest.raises(ValueError):
        monta_digest(_fonte(), braco="tratamento", universo="csv", **BASE)


def test_universo_e_declarado_nao_inferido() -> None:
    fonte = _fonte(_linha("1", "2", "c1"))
    d = monta_digest(fonte, braco="tratamento", universo="state", **BASE)
    assert d.universo == "state"


def test_universo_state_e_csv_produzem_hash_diferente() -> None:
    from harness.digest import digest_hash

    fonte = _fonte(_linha("1", "2", "c1"))
    a = monta_digest(fonte, braco="tratamento", universo="state", **BASE)
    b = monta_digest(fonte, braco="tratamento", universo="csv", **BASE)
    assert digest_hash(a.como_dict()) != digest_hash(b.como_dict())


# --- agregados que antes so existiam em linha bruta (Z0 morre em 30 dias) ---


def test_optout_conta_mas_nao_entra_no_funil() -> None:
    fonte = _fonte(_linha("1", "2", "c1"), _linha("2", "7", "c2"), _linha("3", "7", "c3"))
    d = monta_digest(fonte, braco="tratamento", universo="csv", **BASE)
    assert "optout" not in [e.nome for e in d.bracos[0].etapas]
    assert d.bracos[0].optout == Numero(Decimal("2"), "medido")


def test_optout_dedupe_por_communication_id_e_fact_type() -> None:
    fonte = _fonte(_linha("1", "7", "c1"), _linha("1", "7", "c1"))  # retentativa tecnica
    d = monta_digest(fonte, braco="tratamento", universo="csv", **BASE)
    assert d.bracos[0].optout == Numero(Decimal("1"), "medido")


def test_optout_zero_e_medido_nunca_ausente() -> None:
    """Zero optout na fonte lida ainda e [medido] -- monta_digest sempre
    marca medido quando a fonte foi lida, nunca deixa ausente."""
    fonte = _fonte(_linha("1", "2", "c1"))
    d = monta_digest(fonte, braco="tratamento", universo="csv", **BASE)
    assert d.bracos[0].optout == Numero(Decimal("0"), "medido")


def test_latencia_entrega_clique_bucket_correto() -> None:
    fonte = _fonte(
        _linha("1", "6", "c1", "Mon Jul 28 2026 11:00:00 GMT+0"),
        _linha("1", "4", "c1", "Mon Jul 28 2026 11:00:30 GMT+0"),  # 30s depois
    )
    d = monta_digest(fonte, braco="tratamento", universo="csv", **BASE)
    histograma = dict(d.bracos[0].latencia_entrega_clique)
    assert histograma["1-60s"] == Numero(Decimal("1"), "medido")
    assert sum(int(n.valor or 0) for n in histograma.values()) == 1


def test_latencia_todos_os_baldes_sempre_presentes_e_medidos_mesmo_zerados() -> None:
    fonte = _fonte(_linha("1", "2", "c1"))  # sem DELIVERED nem CLICK
    d = monta_digest(fonte, braco="tratamento", universo="csv", **BASE)
    histograma = dict(d.bracos[0].latencia_entrega_clique)
    assert set(histograma) == set(ORDEM_BUCKETS_LATENCIA)
    assert all(n == Numero(Decimal("0"), "medido") for n in histograma.values())
