import importlib.util

import pytest

from harness.ingest.pg import _driver


def test_exige_psycopg_recusa_quando_driver_ausente() -> None:
    """Ambiente de teste nao instala psycopg (Postgres e optional-dependency)."""
    with pytest.raises(_driver.DriverAusente):
        _driver.exige_psycopg()


def test_exige_psycopg_aceita_quando_driver_presente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda nome: object())
    _driver.exige_psycopg()


def test_dsn_da_casa_le_variavel_por_casa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARNESS_PG_DSN_BRAND_A", "postgresql://user:***@db.example/db")
    assert _driver.dsn_da_casa("brand_a") == "postgresql://user:***@db.example/db"


def test_dsn_da_casa_recusa_sem_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARNESS_PG_DSN_BRAND_A", raising=False)
    with pytest.raises(_driver.CredencialAusente):
        _driver.dsn_da_casa("brand_a")


def test_dsn_da_casa_recusa_variavel_vazia(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARNESS_PG_DSN_BRAND_A", "")
    with pytest.raises(_driver.CredencialAusente):
        _driver.dsn_da_casa("brand_a")
