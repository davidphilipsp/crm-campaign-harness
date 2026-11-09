import json
from decimal import Decimal
from pathlib import Path

import pytest

from harness.cli import build_parser, roda_preflight, roda_publica
from harness.contracts import Braco, Digest, EtapaFunil, Numero
from harness.ingest.pii_guard import PIIEncontrada
from harness.lint.contratos import AchadoUnificado
from harness.persist.resultados import grava_resultado, grava_risco
from harness.pisos import Piso
from harness.risco.contratos import SegmentoRisco, VeredictoRisco

INI, FIM = "2026-07-01T00:00:00Z", "2026-07-08T00:00:00Z"


def _digest(hipotese: str = "h") -> Digest:
    e = EtapaFunil("enviado", Numero(Decimal("100"), "medido"))
    return Digest(
        casa="brand_a", fase="leitura", universo="csv", campanha_id="9000001",
        janela_inicio=INI, janela_fim=FIM, hipotese=hipotese, contexto="",
        bracos=(Braco("tratamento", (e,)),),
        proveniencia={"fonte": "csv", "caminho": "x.csv", "sha256": "a" * 64},
    )


_ARGS_PREFLIGHT_BASE = [
    "preflight",
    "--casa", "brand_a", "--universo", "csv", "--regua", "reativacao-30d",
    "--base-estimada", "150000", "--pct-holdout", "0.05",
    "--conversao-esperada", "0.03",
    "--fonte-conversao-controle", "evento_atribuido",
    "--max-duration-s", "86400", "--delays-s", "3600,7200",
    "--piso-mde-ok", "0.25",
]


def test_publica_dry_run_nao_exige_env_nem_toca_rede(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("CONSUMER_URL", raising=False)
    monkeypatch.delenv("CONSUMER_HARNESS_KEY", raising=False)
    grava_resultado(_digest(), saida=tmp_path)

    args = build_parser().parse_args(["publica", "--entrada", str(tmp_path), "--dry-run"])
    roda_publica(args)

    saida = capsys.readouterr().out
    assert "dry-run" in saida
    assert "nao enviado" in saida


def test_publica_dry_run_recusa_com_pii(tmp_path: Path) -> None:
    grava_resultado(_digest(hipotese="o cliente 12345678909 sempre converte"), saida=tmp_path)
    args = build_parser().parse_args(["publica", "--entrada", str(tmp_path), "--dry-run"])
    with pytest.raises(PIIEncontrada):
        roda_publica(args)


def test_publica_dry_run_sem_resultados_monta_documento_vazio(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = build_parser().parse_args(["publica", "--entrada", str(tmp_path), "--dry-run"])
    roda_publica(args)
    assert "0 leituras" in capsys.readouterr().out


def test_roda_preflight_grava_com_fase_preflight(tmp_path: Path) -> None:
    args = build_parser().parse_args([*_ARGS_PREFLIGHT_BASE, "--saida", str(tmp_path)])
    roda_preflight(args)
    (caminho,) = sorted(tmp_path.glob("*/*/*.json"))
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados["spec"]["fase"] == "preflight"
    assert dados["c8"]["piso_mde_ok"]["origem"] == "cli"
    assert dados["c9"] is not None
    assert dados["c11"] is not None


def test_publica_junta_preflight_e_leitura_separando_por_fase(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    grava_resultado(_digest(), saida=tmp_path)
    roda_preflight(build_parser().parse_args([*_ARGS_PREFLIGHT_BASE, "--saida", str(tmp_path)]))

    args = build_parser().parse_args(["publica", "--entrada", str(tmp_path), "--dry-run"])
    roda_publica(args)

    saida = capsys.readouterr().out
    assert "1 preflights" in saida
    assert "1 leituras" in saida


def _proveniencia_squad() -> dict[str, str]:
    return {
        "fonte": "squad", "squad": "brand-a-risk-squad",
        "caminho": "x.json", "sha256": "a" * 64,
    }


def _veredicto_risco() -> VeredictoRisco:
    return VeredictoRisco(
        fase="risco", casa="brand_a", squad="brand-a-risk-squad", acao="antichurn-bigbass-low",
        janela_inicio="2026-08-06T00:27:00Z", janela_fim="2026-08-07T01:34:03Z",
        segmentos=(
            SegmentoRisco(
                nome="low", custo_total=Decimal("6823.72"), unidades_ofertadas=8039,
                unidades_usadas=6328, taxa_aproveitamento=Decimal("0.787"),
                turnover_atribuido=None,
            ),
        ),
        cobertura_pct=Numero(Decimal("0.99"), "medido"),
        cobertura_piso=Piso(Decimal("0.90"), "default_nao_validado"),
        cobertura_ok=True,
        vies_selecao=None,
        achados_governanca=(),
        proveniencia=_proveniencia_squad(),
    )


def test_publica_le_risco_e_conta_no_resumo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    grava_risco(_veredicto_risco(), saida=tmp_path)

    args = build_parser().parse_args(["publica", "--entrada", str(tmp_path), "--dry-run"])
    roda_publica(args)

    saida = capsys.readouterr().out
    assert "1 riscos" in saida
    assert "0 leituras" in saida


def test_publica_risco_nao_e_confundido_com_leitura(tmp_path: Path) -> None:
    grava_risco(_veredicto_risco(), saida=tmp_path)
    args = build_parser().parse_args(["publica", "--entrada", str(tmp_path), "--dry-run"])
    # nao deve levantar KeyError tentando ler "digest" de um envelope "risco"
    roda_publica(args)


def test_publica_recusa_com_pii_no_achado_de_governanca_do_risco(tmp_path: Path) -> None:
    veredicto = VeredictoRisco(
        fase="risco", casa="brand_a", squad="brand-a-risk-squad", acao="a",
        janela_inicio="2026-08-06T00:27:00Z", janela_fim="2026-08-07T01:34:03Z",
        segmentos=(
            SegmentoRisco(
                nome="x", custo_total=Decimal("1"), unidades_ofertadas=1,
                unidades_usadas=1, taxa_aproveitamento=Decimal("1"),
            ),
        ),
        cobertura_pct=Numero(Decimal("0.99"), "medido"),
        cobertura_piso=Piso(Decimal("0.90"), "default_nao_validado"),
        cobertura_ok=True,
        vies_selecao=None,
        achados_governanca=(
            AchadoUnificado(
                origem="linha_nao_paga", resumo="cliente 12345678909 reclamou", evidencia={},
            ),
        ),
        proveniencia=_proveniencia_squad(),
    )
    grava_risco(veredicto, saida=tmp_path)
    args = build_parser().parse_args(["publica", "--entrada", str(tmp_path), "--dry-run"])
    with pytest.raises(PIIEncontrada):
        roda_publica(args)


def test_publica_recusa_com_pii_no_motivo_do_preflight(tmp_path: Path) -> None:
    from harness.persist.resultados import grava_preflight
    from harness.preflight import SpecCampanha, VeredictoPreflight

    spec = SpecCampanha(
        fase="preflight", casa="brand_a", universo="csv", regua="r",
        base_estimada=1000, pct_holdout=Decimal("0.05"),
        conversao_esperada=Decimal("0.03"), fonte_conversao_controle="ausente",
        max_duration_s=100, delays_s=(10,),
    )
    c11 = VeredictoPreflight(check="C11", aprova=False, motivo="cliente 12345678909 reclamou")
    grava_preflight(spec, saida=tmp_path, c11=c11)

    pub_args = build_parser().parse_args(["publica", "--entrada", str(tmp_path), "--dry-run"])
    with pytest.raises(PIIEncontrada):
        roda_publica(pub_args)
