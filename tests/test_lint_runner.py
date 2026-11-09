from decimal import Decimal

import pytest

from harness.contracts import (
    ORDEM_BUCKETS_LATENCIA,
    Braco,
    BucketLatencia,
    Digest,
    EtapaFunil,
    Numero,
)
from harness.lint import c3 as c3_modulo
from harness.lint import runner
from harness.lint.runner import PisoAusente, roda_lint
from harness.pisos import Piso

INI, FIM = "2026-07-01T00:00:00Z", "2026-07-08T00:00:00Z"

PISO_C3 = Piso(Decimal("0.85"), "crm_md")
PISO_C2 = Piso(Decimal("0.05"), "crm_md")
PISO_CTOR = Piso(Decimal("0.60"), "crm_md")

PISOS_COMPLETOS = {"C3_ENTREGA_MINIMA": PISO_C3, "C2_DESVIO_MAX_BRACOS": PISO_C2}


def _e(nome: str, v: str) -> EtapaFunil:
    return EtapaFunil(nome, Numero(Decimal(v), "medido"))  # type: ignore[arg-type]


def _histograma(**contagens: int) -> tuple[tuple[BucketLatencia, Numero], ...]:
    return tuple(
        (nome, Numero(Decimal(contagens.get(nome, 0)), "medido"))
        for nome in ORDEM_BUCKETS_LATENCIA
    )


def _digest(*bracos: Braco) -> Digest:
    return Digest(
        casa="brand_a", fase="leitura", universo="csv", campanha_id="9000001",
        janela_inicio=INI, janela_fim=FIM,
        hipotese="h", contexto="", bracos=bracos,
        proveniencia={"fonte": "teste"},
    )


def test_roda_lint_so_com_c2_c3_c6ordem_registrados_e_vermelho_por_ausencia() -> None:
    """ROSTER declara 9 identificadores (C1, C1-b, C2..C6, C6-ordem, C7);
    REGISTRO tem C2, C3 e C6-ordem (item 2). Os outros 6 aparecem no
    resultado como vermelho por ausencia (item 3), nao somem -- e
    vermelho vence a agregacao (item 5). C6-ordem entra aqui tambem, mas
    NAO reduz os 6 ausentes: "C6" propriamente dito continua sem
    implementacao -- C6-ordem e um identificador novo, nao um substituto."""
    braco = Braco("tratamento", (_e("enviado", "1000"), _e("entregue", "950")))
    r = roda_lint(_digest(braco), pisos=PISOS_COMPLETOS)

    assert r.veredito == "vermelho"
    assert len(r.resultados) == len(runner.ROSTER) == 9

    ausentes = [x for x in r.resultados if x.motivo == "gate_nao_implementado"]
    assert len(ausentes) == 6
    assert all(x.veredito == "vermelho" and x.piso_usado is None for x in ausentes)
    assert {x.gate for x in ausentes} == {"C1", "C1-b", "C4", "C5", "C6", "C7"}

    c3 = next(x for x in r.resultados if x.gate == "C3")
    assert c3.veredito == "verde"
    assert c3.motivo == "dado_valido"

    # braco sem latencia_entrega_clique explicito -> default [ausente]
    # (harness/contracts.py) -- C6-ordem roda (nao esta em `ausentes`,
    # motivo != "gate_nao_implementado") mas fica indeterminado, nunca verde.
    c6_ordem = next(x for x in r.resultados if x.gate == "C6-ordem")
    assert c6_ordem.veredito == "indeterminado"
    assert c6_ordem.motivo == "dado_insuficiente"
    assert c6_ordem.piso_usado is None


def test_roster_monkeypatchado_para_so_implementados_e_verde(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com ROSTER reduzido aos 2 gates que tem REGISTRO, e nenhum motivo de
    reprovar (dado suficiente, entrega comparavel), a agregacao vira verde."""
    monkeypatch.setattr(runner, "ROSTER", ("C2", "C3"))
    tratamento = Braco("tratamento", (_e("enviado", "1000"), _e("entregue", "950")))
    comparacao = Braco("comparacao", (_e("enviado", "1000"), _e("entregue", "940")))

    r = roda_lint(_digest(tratamento, comparacao), pisos=PISOS_COMPLETOS)

    assert r.veredito == "verde"
    assert {x.gate for x in r.resultados} == {"C2", "C3"}
    assert all(x.veredito == "verde" for x in r.resultados)


def test_vermelho_de_gate_vence_verde(monkeypatch: pytest.MonkeyPatch) -> None:
    """C3 vermelho (dado invalido: entregue > enviado) tem que vencer C2
    verde na agregacao -- nao e so o mecanismo de ausencia (item 3) que
    produz vermelho, o proprio veredito de gate tambem precisa vencer."""
    monkeypatch.setattr(runner, "ROSTER", ("C2", "C3"))
    tratamento = Braco("tratamento", (_e("enviado", "100"), _e("entregue", "150")))
    comparacao = Braco("comparacao", (_e("enviado", "100"), _e("entregue", "90")))

    r = roda_lint(_digest(tratamento, comparacao), pisos=PISOS_COMPLETOS)

    assert r.veredito == "vermelho"
    c3 = next(x for x in r.resultados if x.gate == "C3")
    assert c3.veredito == "vermelho"
    assert c3.motivo == "dado_invalido"


def test_achados_de_gate_e_de_detector_chegam_no_mesmo_canal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C3 abaixo do piso anexa achado (verde, nao rebaixa); ctor_anomalo
    (detector B, agora lido do Digest -- aberto/clicado/latencia ja
    agregados por monta_digest, nao mais linha bruta) tambem produz
    achado -- os dois tem que aparecer juntos em ResultadoLint.achados,
    sem canal separado. optout_alto fica pendente (sem piso_optout em
    `pisos`) e nao aparece nem quebra a execucao."""
    monkeypatch.setattr(runner, "ROSTER", ("C3",))
    braco = Braco(
        "tratamento",
        (_e("enviado", "7268"), _e("entregue", "4796"), _e("aberto", "2"), _e("clicado", "2")),
        _histograma(**{"1-60s": 2}),
    )
    pisos = {"C3_ENTREGA_MINIMA": PISO_C3, "CTOR_MAX_ANOMALO": PISO_CTOR}

    r = roda_lint(_digest(braco), pisos=pisos)

    origens = {a.origem for a in r.achados}
    assert "C3" in origens
    assert "ctor_anomalo" in origens
    assert "optout_alto" not in origens


def test_gate_registrado_sem_piso_injetado_estoura_pisoausente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Diferente do detector B (pendente sem levantar), um gate do REGISTRO
    tem contrato firme com seu piso -- rodar sem ele e erro de wiring."""
    monkeypatch.setattr(runner, "ROSTER", ("C3",))
    braco = Braco("tratamento", (_e("enviado", "1000"), _e("entregue", "950")))

    with pytest.raises(PisoAusente):
        roda_lint(_digest(braco), pisos={})


def test_fallback_de_carrega_piso_em_c3_e_inalcancavel_a_partir_do_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """c3.py ainda tem `piso if piso is not None else carrega_piso(...)`
    (item 6: fica onde esta por ora). O runner sempre resolve e injeta os
    pisos primeiro -- carrega_piso (I/O, le CRM.md) nunca deveria ser
    chamado partindo do runner. Monkeypatch para estourar se for."""

    def _carrega_piso_nao_deveria_ser_chamado(nome: str, **_: object) -> Piso:
        raise AssertionError(
            f"carrega_piso({nome!r}) chamado a partir do runner -- fallback "
            "de c3.py deveria ser inalcancavel quando o piso vem de `pisos`"
        )

    monkeypatch.setattr(c3_modulo, "carrega_piso", _carrega_piso_nao_deveria_ser_chamado)
    braco = Braco("tratamento", (_e("enviado", "1000"), _e("entregue", "950")))

    r = roda_lint(_digest(braco), pisos=PISOS_COMPLETOS)

    assert r.veredito == "vermelho"  # 6 gates ausentes ainda dominam -- so prova que nao estourou
