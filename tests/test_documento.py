import json
from decimal import Decimal
from pathlib import Path

from harness.contracts import Braco, EtapaFunil, Numero
from harness.lint.achados import Achado as AchadoLint
from harness.lint.c3 import Achado as AchadoC3
from harness.lint.c3 import ResultadoC3
from harness.lint.contratos import AchadoUnificado
from harness.pisos import Piso
from harness.preflight import ResultadoMDE, VeredictoPreflight
from harness.publica.documento import (
    ResultadoLeitura,
    ResultadoPreflight,
    ResultadoRisco,
    monta_documento,
)
from harness.risco.contratos import SegmentoRisco

# documento_v1 e documento_v2 ficam congelados como registro historico
# (nenhum teste os le mais desde a E24), mesmo raciocinio do B0 em CRM.md
# ("fixture orfa"). O golden ativo agora e documento_v3: preflights/leituras
# identicos byte a byte, so a forma de riscos[].cobertura_pct muda (Decimal
# cru -> Numero, pra ter um rotulo "ausente" honesto).
GOLDEN = Path(__file__).parent / "golden" / "documento_v3" / "esperado.json"


def _preflight_do_exemplo() -> ResultadoPreflight:
    return ResultadoPreflight(
        casa="brand_a",
        universo="csv",
        regua="reativacao-30d",
        base_estimada=150000,
        pct_holdout=Decimal("0.05"),
        conversao_esperada=Decimal("0.03"),
        c8=ResultadoMDE(
            n_holdout=7500,
            n_tratamento=142500,
            mde_absoluto=Decimal("0.0057"),
            mde_relativo=Decimal("0.19"),
            veredito="OK",
            piso_amostra=Piso(Decimal("30"), "default_nao_validado"),
            piso_mde_ok=Piso(Decimal("0.25"), "crm_md"),
            alternativas=(),
        ),
        c9=VeredictoPreflight(check="C9", aprova=True, motivo=""),
        c11=VeredictoPreflight(
            check="C11", aprova=False,
            motivo="max_duration_s=86400 < soma(delays_s)=136800",
        ),
    )


def _leitura_do_exemplo() -> ResultadoLeitura:
    bracos = (
        Braco("tratamento", (
            EtapaFunil("enviado", Numero(Decimal("727"), "medido")),
            EtapaFunil("entregue", Numero(Decimal("480"), "medido")),
            EtapaFunil("aberto", Numero(Decimal("111"), "medido")),
            EtapaFunil("clicado", Numero(Decimal("105"), "medido")),
        )),
    )
    c3 = ResultadoC3(
        veredito="verde",
        piso_usado=Piso(Decimal("0.85"), "default_nao_validado"),
        achados=(
            AchadoC3(
                gate="C3", braco="tratamento",
                resumo="entrega=0.66 abaixo do piso 0.85 (origem=default_nao_validado)",
                evidencia={"enviado": Decimal("727"), "entregue": Decimal("480")},
            ),
        ),
    )
    achados = (
        AchadoLint(
            tipo="ctor_anomalo",
            resumo="CLICK/IMPRESSION=0.94 acima do piso 0.60 (origem=default_nao_validado)",
            evidencia={
                "<=0s": 12, "1-60s": 80, "61-3600s": 9, "3601-86400s": 3, ">86400s": 1,
            },
        ),
    )
    return ResultadoLeitura(
        casa="brand_a",
        universo="csv",
        campanha_id="9000001",
        janela_inicio="2026-07-01T00:00:00Z",
        janela_fim="2026-07-28T00:00:00Z",
        hipotese="oferta converte mais que a generica",
        contexto="",
        digest_hash="5c34df85a14250380c2a4e08a890ca7cdef261ea0036f81742271428ff865a2c",
        bracos=bracos,
        c3=c3,
        c2=None,
        achados=achados,
    )


def _risco_do_exemplo() -> ResultadoRisco:
    return ResultadoRisco(
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
            origem="vies_selecao",
            resumo="exposto ja era mais ativo que o controle antes da campanha",
            evidencia={"turnover_exposto_pre": "1200.00", "turnover_controle_pre": "450.00"},
        ),
        achados_governanca=(
            AchadoUnificado(
                origem="linha_nao_paga", resumo="Missao Artemis nunca foi paga",
                evidencia={"torneio": "Missao Artemis", "valor_nominal": "25000.00"},
            ),
        ),
    )


def test_monta_documento_bate_com_o_golden_do_contrato_v3() -> None:
    documento = monta_documento(
        preflights=(_preflight_do_exemplo(),),
        leituras=(_leitura_do_exemplo(),),
        riscos=(_risco_do_exemplo(),),
        gerado_em="2026-08-01T12:00:00Z",
        harness_commit="87076b5",
    )
    esperado = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(documento)) == esperado


def test_monta_documento_versao_e_sempre_3() -> None:
    doc = monta_documento(preflights=(), leituras=(), gerado_em="x", harness_commit="y")
    assert doc["versao"] == 3


def test_monta_documento_vazio_e_documento_valido_minimo() -> None:
    doc = monta_documento(preflights=(), leituras=(), gerado_em="x", harness_commit="y")
    assert doc["preflights"] == []
    assert doc["leituras"] == []
    assert doc["riscos"] == []


def test_monta_documento_risco_com_vies_selecao_ausente_vira_null() -> None:
    risco = ResultadoRisco(
        casa="brand_a", squad="brand-a-risk-squad", acao="a",
        janela_inicio="2026-01-01T00:00:00Z", janela_fim="2026-01-02T00:00:00Z",
        segmentos=(
            SegmentoRisco(
                nome="x", custo_total=Decimal("1"), unidades_ofertadas=1,
                unidades_usadas=1, taxa_aproveitamento=Decimal("1"),
            ),
        ),
        cobertura_pct=Numero(Decimal("0.99"), "medido"),
        cobertura_piso=Piso(Decimal("0.90"), "default_nao_validado"),
        cobertura_ok=True,
    )
    doc = monta_documento(
        preflights=(), leituras=(), riscos=(risco,), gerado_em="x", harness_commit="y",
    )
    assert doc["riscos"][0]["vies_selecao"] is None  # type: ignore[index]
    assert doc["riscos"][0]["achados_governanca"] == []  # type: ignore[index]


def test_monta_documento_cobertura_ausente_vira_valor_null_rotulo_ausente() -> None:
    risco = ResultadoRisco(
        casa="brand_a", squad="brand-a-risk-squad", acao="a",
        janela_inicio="2026-01-01T00:00:00Z", janela_fim="2026-01-02T00:00:00Z",
        segmentos=(
            SegmentoRisco(
                nome="x", custo_total=Decimal("1"), unidades_ofertadas=1,
                unidades_usadas=1, taxa_aproveitamento=Decimal("1"),
            ),
        ),
        cobertura_pct=Numero(None, "ausente"),
        cobertura_piso=Piso(Decimal("0.90"), "default_nao_validado"),
        cobertura_ok=False,
    )
    doc = monta_documento(
        preflights=(), leituras=(), riscos=(risco,), gerado_em="x", harness_commit="y",
    )
    assert doc["riscos"][0]["cobertura_pct"] == {"valor": None, "rotulo": "ausente"}  # type: ignore[index]


def test_monta_documento_nunca_deixa_decimal_cru() -> None:
    documento = monta_documento(
        preflights=(_preflight_do_exemplo(),),
        leituras=(_leitura_do_exemplo(),),
        gerado_em="2026-08-01T12:00:00Z",
        harness_commit="87076b5",
    )

    def _sem_decimal(no: object) -> bool:
        if isinstance(no, Decimal):
            return False
        if isinstance(no, dict):
            return all(_sem_decimal(v) for v in no.values())
        if isinstance(no, list):
            return all(_sem_decimal(v) for v in no)
        return True

    assert _sem_decimal(documento)


def test_monta_documento_c2_e_c8_ausentes_viram_null() -> None:
    leitura = ResultadoLeitura(
        casa="brand_a", universo="csv", campanha_id="x",
        janela_inicio="2026-01-01T00:00:00Z", janela_fim="2026-01-08T00:00:00Z",
        hipotese="h", contexto="", digest_hash="a" * 64, bracos=(),
    )
    preflight = ResultadoPreflight(
        casa="brand_a", universo="csv", regua="r", base_estimada=100,
        pct_holdout=Decimal("0.1"), conversao_esperada=Decimal("0.1"),
    )
    doc = monta_documento(
        preflights=(preflight,), leituras=(leitura,), gerado_em="x", harness_commit="y",
    )
    assert doc["leituras"][0]["c2"] is None  # type: ignore[index]
    assert doc["leituras"][0]["c3"] is None  # type: ignore[index]
    assert doc["preflights"][0]["c8"] is None  # type: ignore[index]
