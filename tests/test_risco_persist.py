import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from harness.contracts import Numero
from harness.lint.contratos import AchadoUnificado
from harness.persist.resultados import eh_preflight, eh_risco, grava_risco, le_risco
from harness.pisos import Piso
from harness.risco.contratos import SegmentoRisco, VeredictoRisco


def _veredicto(**overrides: object) -> VeredictoRisco:
    base: dict[str, object] = dict(
        fase="risco",
        casa="brand_a",
        squad="brand-a-risk-squad",
        acao="antichurn-bigbass-low",
        janela_inicio="2026-08-06T00:27:00Z",
        janela_fim="2026-08-07T01:34:03Z",
        segmentos=(
            SegmentoRisco(
                nome="low", custo_total=Decimal("6823.72"),
                unidades_ofertadas=8039, unidades_usadas=6328,
                taxa_aproveitamento=Decimal("0.787"), turnover_atribuido=None,
            ),
        ),
        cobertura_pct=Numero(Decimal("0.795"), "medido"),
        cobertura_piso=Piso(Decimal("0.90"), "default_nao_validado"),
        cobertura_ok=False,
        vies_selecao=AchadoUnificado(
            origem="vies_selecao", resumo="exposto mais ativo pre-campanha",
            evidencia={"turnover_exposto_pre": "1200.00"},
        ),
        achados_governanca=(
            AchadoUnificado(
                origem="linha_nao_paga", resumo="Missao Artemis nunca foi paga",
                evidencia={"torneio": "Missao Artemis"},
            ),
        ),
        proveniencia={
            "fonte": "squad", "squad": "brand-a-risk-squad",
            "caminho": "x.json", "sha256": "a" * 64,
        },
    )
    base.update(overrides)
    return VeredictoRisco(**base)  # type: ignore[arg-type]


def test_grava_risco_no_caminho_esperado(tmp_path: Path) -> None:
    agora = datetime(2026, 8, 10, 12, tzinfo=UTC)
    caminho = grava_risco(_veredicto(), saida=tmp_path, agora=agora)
    assert caminho == tmp_path / "brand_a" / "antichurn-bigbass-low" / "20260810T120000.000000Z.json"
    assert caminho.exists()


def test_grava_risco_envelope_tem_chave_risco_e_fase_risco(tmp_path: Path) -> None:
    caminho = grava_risco(_veredicto(), saida=tmp_path)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados["risco"]["fase"] == "risco"
    assert eh_risco(dados)
    assert not eh_preflight(dados)


def test_grava_risco_nunca_sobrescreve(tmp_path: Path) -> None:
    agora = datetime(2026, 8, 10, tzinfo=UTC)
    grava_risco(_veredicto(), saida=tmp_path, agora=agora)
    with pytest.raises(FileExistsError):
        grava_risco(_veredicto(), saida=tmp_path, agora=agora)


def test_le_risco_reconstroi_o_que_grava_risco_escreveu(tmp_path: Path) -> None:
    original = _veredicto()
    caminho = grava_risco(original, saida=tmp_path)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert le_risco(dados["risco"]) == original


def test_le_risco_reconstroi_vies_selecao_ausente(tmp_path: Path) -> None:
    original = _veredicto(vies_selecao=None)
    caminho = grava_risco(original, saida=tmp_path)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert le_risco(dados["risco"]).vies_selecao is None


def test_le_risco_reconstroi_cobertura_ausente(tmp_path: Path) -> None:
    original = _veredicto(cobertura_pct=Numero(None, "ausente"), cobertura_ok=False)
    caminho = grava_risco(original, saida=tmp_path)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    reconstruido = le_risco(dados["risco"])
    assert reconstruido.cobertura_pct == Numero(None, "ausente")
    assert reconstruido == original


def test_veredicto_risco_recusa_fase_diferente_de_risco() -> None:
    with pytest.raises(ValueError, match="fase == 'risco'"):
        _veredicto(fase="leitura")


def test_veredicto_risco_recusa_sem_segmentos() -> None:
    with pytest.raises(ValueError, match="ao menos um segmento"):
        _veredicto(segmentos=())
