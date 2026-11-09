"""'harness query' (E22, CRM.md): consumidor do catalogo (E8) + FontePostgres
(E9). Validacao de nome/params tem que falhar antes de tocar driver ou rede
-- provado aqui sem psycopg instalado e sem HARNESS_PG_DSN_BRAND_A setada."""

from pathlib import Path

import pytest

import harness.ingest.pg as pg_module
from harness.cli import ParametroMalFormado, ParametrosDivergentes, build_parser, roda_query
from harness.ingest.pg._driver import DriverAusente


def _args(*extra: str) -> list[str]:
    return ["query", *extra]


def test_query_recusa_nome_desconhecido() -> None:
    args = build_parser().parse_args(_args("query_que_nao_existe", "--casa", "brand_a"))
    with pytest.raises(ValueError, match="desconhecida"):
        roda_query(args)


def test_query_recusa_param_mal_formado() -> None:
    args = build_parser().parse_args(
        _args("executive_kpis", "--casa", "brand_a", "--param", "sem_igual")
    )
    with pytest.raises(ParametroMalFormado):
        roda_query(args)


def test_query_recusa_params_faltando() -> None:
    args = build_parser().parse_args(
        _args("executive_kpis", "--casa", "brand_a",
              "--param", "janela_inicio=2026-01-01")
    )
    with pytest.raises(ParametrosDivergentes, match="faltando=\\['janela_fim'\\]"):
        roda_query(args)


def test_query_recusa_params_sobrando() -> None:
    args = build_parser().parse_args(
        _args("client_field_profile", "--casa", "brand_a",
              "--param", "sample_size=100", "--param", "extra=1")
    )
    with pytest.raises(ParametrosDivergentes, match="sobrando=\\['extra'\\]"):
        roda_query(args)


def test_query_com_params_corretos_so_falha_no_driver_ausente() -> None:
    """Prova que a validacao de params passou e o codigo chegou ate
    FontePostgres.linhas() -- so falha porque psycopg nao esta instalado
    neste ambiente de teste (Postgres e optional-dependency)."""
    args = build_parser().parse_args(
        _args("executive_kpis", "--casa", "brand_a",
              "--param", "janela_inicio=2026-01-01", "--param", "janela_fim=2026-01-31")
    )
    with pytest.raises(DriverAusente):
        roda_query(args)


class _FontePostgresFake:
    def __init__(self, *, casa: str, query: object, params: dict[str, str]) -> None:
        self.casa = casa
        self.query = query
        self.params = params

    def linhas(self) -> list[dict[str, str]]:
        return [{"provider_name": "pragmatic", "ggr": "100"}]

    def proveniencia(self) -> dict[str, str]:
        return {"fonte": "postgres", "casa": self.casa, "query": "provider_performance"}


def test_query_formato_csv_para_stdout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(pg_module, "FontePostgres", _FontePostgresFake)
    args = build_parser().parse_args(
        _args("provider_performance", "--casa", "brand_a",
              "--param", "janela_inicio=2026-01-01", "--param", "janela_fim=2026-01-31")
    )
    roda_query(args)
    saida = capsys.readouterr().out
    assert "provider_name,ggr" in saida
    assert "pragmatic,100" in saida


def test_query_formato_json_grava_arquivo_com_proveniencia(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(pg_module, "FontePostgres", _FontePostgresFake)
    destino = tmp_path / "saida.json"
    args = build_parser().parse_args(
        _args("provider_performance", "--casa", "brand_a",
              "--param", "janela_inicio=2026-01-01", "--param", "janela_fim=2026-01-31",
              "--formato", "json", "--saida", str(destino))
    )
    roda_query(args)
    conteudo = destino.read_text(encoding="utf-8")
    assert '"query": "provider_performance"' in conteudo
    assert '"ggr": "100"' in conteudo
