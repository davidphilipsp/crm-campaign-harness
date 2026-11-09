import json
from pathlib import Path

import pytest

from harness.cli import build_parser, roda_risco
from harness.risco.ingestao import ChavesDivergentes


def _payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "casa": "brand_b",
        "squad": "brand-b-financial-squad",
        "acao": "antichurn-bigbass-medium",
        "janela_inicio": "2026-08-06T00:00:00Z",
        "janela_fim": "2026-08-07T00:00:00Z",
        "segmentos": [
            {
                "nome": "medium",
                "custo_total": "23558.35",
                "unidades_ofertadas": 20000,
                "unidades_usadas": 11240,
                "taxa_aproveitamento": "0.562",
                "turnover_atribuido": None,
            }
        ],
        "cobertura_pct": {"valor": "0.99", "rotulo": "medido"},
        "vies_selecao": None,
        "achados_governanca": [],
    }
    base.update(overrides)
    return base


def test_roda_risco_grava_resultado_e_imprime_status(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entrada = tmp_path / "veredicto.json"
    entrada.write_text(json.dumps(_payload()), encoding="utf-8")
    saida = tmp_path / "resultados"

    args = build_parser().parse_args(["risco", str(entrada), "--saida", str(saida)])
    roda_risco(args)

    (caminho,) = sorted(saida.glob("*/*/*.json"))
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados["risco"]["squad"] == "brand-b-financial-squad"
    assert dados["risco"]["cobertura_ok"] is True

    out = capsys.readouterr().out
    assert "squad=brand-b-financial-squad" in out
    assert "-> ok" in out
    assert "gravado:" in out


def test_roda_risco_cobertura_abaixo_do_piso_imprime_suspenso(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entrada = tmp_path / "veredicto.json"
    payload = _payload(cobertura_pct={"valor": "0.5", "rotulo": "medido"})
    entrada.write_text(json.dumps(payload), encoding="utf-8")

    args = build_parser().parse_args(
        ["risco", str(entrada), "--saida", str(tmp_path / "resultados")]
    )
    roda_risco(args)

    assert "suspenso" in capsys.readouterr().out


def test_roda_risco_cobertura_ausente_imprime_suspenso_sem_quebrar(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """E24: caso real dos relatorios de AntiChurn -- sessao encerrada, sem
    numero de cobertura. 'harness risco' aceita e mostra suspenso, nunca
    recusa por falta de numero (ausente e um rotulo valido)."""
    entrada = tmp_path / "veredicto.json"
    payload = _payload(cobertura_pct={"valor": None, "rotulo": "ausente"})
    entrada.write_text(json.dumps(payload), encoding="utf-8")

    args = build_parser().parse_args(
        ["risco", str(entrada), "--saida", str(tmp_path / "resultados")]
    )
    roda_risco(args)

    out = capsys.readouterr().out
    assert "ausente" in out
    assert "suspenso" in out


def test_roda_risco_recusa_arquivo_mal_formado(tmp_path: Path) -> None:
    entrada = tmp_path / "veredicto.json"
    payload = _payload()
    del payload["cobertura_pct"]
    entrada.write_text(json.dumps(payload), encoding="utf-8")

    args = build_parser().parse_args(
        ["risco", str(entrada), "--saida", str(tmp_path / "resultados")]
    )
    with pytest.raises(ChavesDivergentes):
        roda_risco(args)
