"""C6-ordem: unidade (Braco construido a mao) + fecha a fixture orfa
tests/golden/latencia_impossivel/entrada.csv (gerada, sem leitor de
conteudo ate este commit -- so o round-trip byte a byte em
test_gera_golden.py a tocava)."""

import json
from decimal import Decimal
from pathlib import Path

from harness.contracts import (
    ORDEM_BUCKETS_LATENCIA,
    Braco,
    BucketLatencia,
    Digest,
    EtapaFunil,
    Numero,
)
from harness.ingest.agrega import monta_digest
from harness.ingest.fonte_csv import FonteCSV
from harness.lint.ordem_temporal import avalia_ordem_temporal
from harness.lint.runner import roda_lint
from harness.persist.resultados import grava_resultado
from harness.pisos import Piso

COLS = ("user_ext_id", "fact_type_id", "communication_id")


def _histograma(**contagens: int) -> tuple[tuple[BucketLatencia, Numero], ...]:
    return tuple(
        (nome, Numero(Decimal(contagens.get(nome, 0)), "medido"))
        for nome in ORDEM_BUCKETS_LATENCIA
    )


def _e(nome: str, v: str) -> EtapaFunil:
    return EtapaFunil(nome, Numero(Decimal(v), "medido"))  # type: ignore[arg-type]


def _digest(*bracos: Braco) -> Digest:
    return Digest(
        casa="brand_a", fase="leitura", universo="csv", campanha_id="x",
        janela_inicio="2026-07-01T00:00:00Z", janela_fim="2026-07-08T00:00:00Z",
        hipotese="h", contexto="", bracos=bracos,
        proveniencia={"fonte": "teste"},
    )


# --- unidade: Braco construido a mao -----------------------------------


def test_com_zero_em_menos_igual_zero_s_e_medido_da_verde() -> None:
    braco = Braco("tratamento", (_e("entregue", "10"),), _histograma(**{"1-60s": 3}))
    r = avalia_ordem_temporal(_digest(braco))
    assert r.veredito == "verde"
    assert r.achados == ()


def test_com_menos_igual_zero_s_positivo_e_medido_da_vermelho_com_motivo() -> None:
    braco = Braco("tratamento", (_e("entregue", "10"),), _histograma(**{"<=0s": 4}))
    r = avalia_ordem_temporal(_digest(braco))
    assert r.veredito == "vermelho"
    assert len(r.achados) == 1
    achado = r.achados[0]
    assert achado.gate == "C6-ordem"
    assert achado.braco == "tratamento"
    assert achado.evidencia == {"<=0s": 4}
    assert "impossivel" in achado.resumo


def test_ausente_da_indeterminado_nunca_verde() -> None:
    braco = Braco("tratamento", (_e("entregue", "10"),))  # default: latencia [ausente]
    r = avalia_ordem_temporal(_digest(braco))
    assert r.veredito == "indeterminado"
    assert r.achados == ()


def test_um_braco_contaminado_nao_desaparece_com_outro_limpo() -> None:
    """POR BRACO, como C3: um braco vermelho tem que vencer a agregacao
    mesmo com outro braco verde ao lado -- nunca somar/mediar os dois."""
    limpo = Braco("tratamento", (_e("entregue", "10"),), _histograma(**{"1-60s": 5}))
    contaminado = Braco("comparacao", (_e("entregue", "10"),), _histograma(**{"<=0s": 1}))
    r = avalia_ordem_temporal(_digest(limpo, contaminado))
    assert r.veredito == "vermelho"
    assert {a.braco for a in r.achados} == {"comparacao"}


def test_um_braco_ausente_nao_vira_verde_por_causa_de_outro_limpo() -> None:
    limpo = Braco("tratamento", (_e("entregue", "10"),), _histograma(**{"1-60s": 5}))
    ausente = Braco("comparacao", (_e("entregue", "10"),))
    r = avalia_ordem_temporal(_digest(limpo, ausente))
    assert r.veredito == "indeterminado"


# --- fecha a fixture orfa: tests/golden/latencia_impossivel -------------


def _digest_latencia_impossivel() -> Digest:
    return monta_digest(
        FonteCSV(Path("tests/golden/latencia_impossivel/entrada.csv"), colunas_esperadas=COLS),
        braco="tratamento", casa="brand_a", universo="csv", campanha_id="ordem-impossivel",
        janela_inicio="2026-07-01T00:00:00Z", janela_fim="2026-07-28T00:00:00Z",
        hipotese="fixture prova ordem temporal impossivel", contexto="",
    )


def test_golden_latencia_impossivel_tem_30_em_menos_igual_zero_s_medido() -> None:
    d = _digest_latencia_impossivel()
    histograma = dict(d.bracos[0].latencia_entrega_clique)
    assert histograma["<=0s"] == Numero(Decimal("30"), "medido")


def test_golden_latencia_impossivel_da_c6_ordem_vermelho() -> None:
    r = avalia_ordem_temporal(_digest_latencia_impossivel())
    assert r.veredito == "vermelho"
    assert r.achados and r.achados[0].evidencia["<=0s"] == 30


def test_golden_latencia_impossivel_c6_ordem_vermelho_chega_ao_json_persistido(
    tmp_path: Path,
) -> None:
    """Nao basta o gate calcular vermelho em memoria (ja provado acima) --
    ele precisa aparecer no JSON persistido, com causa (motivo), pelo
    canal generico "gates" de grava_resultado."""
    d = _digest_latencia_impossivel()
    resultado_lint = roda_lint(
        d,
        pisos={
            "C3_ENTREGA_MINIMA": Piso(Decimal("0.85"), "default_nao_validado"),
            "C2_DESVIO_MAX_BRACOS": Piso(Decimal("0.05"), "default_nao_validado"),
        },
    )
    caminho = grava_resultado(d, saida=tmp_path, resultado_lint=resultado_lint)
    dados = json.loads(caminho.read_text(encoding="utf-8"))

    c6_ordem = next(g for g in dados["gates"] if g["gate"] == "C6-ordem")
    assert c6_ordem["veredito"] == "vermelho"
    assert c6_ordem["motivo"] == "dado_invalido"
