import pytest

from harness.cli import build_parser


def test_parse_ingest() -> None:
    args = build_parser().parse_args(
        [
            "ingest", "x.csv",
            "--casa", "brand_a",
            "--campanha", "9000001",
            "--braco", "tratamento",
            "--de", "2026-07-01T00:00:00Z",
            "--ate", "2026-07-08T00:00:00Z",
            "--universo", "csv",
            "--hipotese", "h",
        ]
    )
    assert args.comando == "ingest"
    assert args.casa == "brand_a"
    assert args.saida == "resultados"


def test_subcomando_invalido_sai_com_2() -> None:
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["inexistente"])
    assert exc.value.code == 2


def test_parse_preflight() -> None:
    args = build_parser().parse_args(
        [
            "preflight",
            "--casa", "brand_a", "--universo", "csv", "--regua", "reativacao-30d",
            "--base-estimada", "150000", "--pct-holdout", "0.05",
            "--conversao-esperada", "0.03",
            "--fonte-conversao-controle", "evento_atribuido",
            "--max-duration-s", "86400", "--delays-s", "3600,7200",
            "--piso-mde-ok", "0.25",
        ]
    )
    assert args.comando == "preflight"
    assert args.casa == "brand_a"
    assert args.base_estimada == 150000
    assert args.delays_s == "3600,7200"
    assert args.piso_mde_ok == "0.25"
    assert args.saida == "resultados"


def test_parse_publica_defaults() -> None:
    args = build_parser().parse_args(["publica"])
    assert args.comando == "publica"
    assert args.entrada == "resultados"
    assert args.desde is None
    assert args.dry_run is False


def test_parse_publica_com_flags() -> None:
    args = build_parser().parse_args(
        ["publica", "--dry-run", "--desde", "2026-08-01T00:00:00Z", "--entrada", "x"]
    )
    assert args.dry_run is True
    assert args.desde == "2026-08-01T00:00:00Z"
    assert args.entrada == "x"
