from decimal import Decimal

from harness.contracts import ORDEM_BUCKETS_LATENCIA, Braco, BucketLatencia, EtapaFunil, Numero
from harness.lint.achados import detecta_ctor_anomalo, detecta_optout_alto
from harness.pisos import Piso

PISO_CTOR = Piso(Decimal("0.60"), "default_nao_validado")
PISO_OPTOUT = Piso(Decimal("0.05"), "default_nao_validado")


def _e(nome: str, v: str) -> EtapaFunil:
    return EtapaFunil(nome, Numero(Decimal(v), "medido"))  # type: ignore[arg-type]


def _histograma(**contagens: int) -> tuple[tuple[BucketLatencia, Numero], ...]:
    """latencia_entrega_clique com todos os baldes [medido]; baldes nao
    citados em `contagens` ficam 0 (medido, nao ausente)."""
    return tuple(
        (nome, Numero(Decimal(contagens.get(nome, 0)), "medido"))
        for nome in ORDEM_BUCKETS_LATENCIA
    )


def _histograma_ausente() -> tuple[tuple[BucketLatencia, Numero], ...]:
    return tuple((nome, Numero(None, "ausente")) for nome in ORDEM_BUCKETS_LATENCIA)


# --- CTOR anomalo ------------------------------------------------------------
# Le do Digest (braco.etapas + braco.latencia_entrega_clique), nao mais de
# linha bruta -- monta_digest ja agrega os dois por braco.


def test_ctor_abaixo_do_piso_nao_gera_achado() -> None:
    braco = Braco(
        "tratamento", (_e("aberto", "3"), _e("clicado", "1")), _histograma(**{"1-60s": 1}),
    )  # 1/3=0.33 < 0.60
    assert detecta_ctor_anomalo(braco, piso_ctor=PISO_CTOR) is None


def test_ctor_acima_do_piso_gera_achado_com_evidencia() -> None:
    braco = Braco(
        "tratamento", (_e("aberto", "2"), _e("clicado", "2")),  # 2/2 = 1.0 > 0.60
        _histograma(**{"1-60s": 2}),
    )
    achado = detecta_ctor_anomalo(braco, piso_ctor=PISO_CTOR)
    assert achado is not None
    assert achado.tipo == "ctor_anomalo"
    assert achado.evidencia["1-60s"] == 2


def test_ctor_evidencia_e_o_histograma_do_digest_sem_recalcular() -> None:
    """O detector nao repete o trabalho de monta_digest -- so repassa
    braco.latencia_entrega_clique como evidencia, ja pronto."""
    histograma = _histograma(**{"<=0s": 3, "1-60s": 2, ">86400s": 1})
    braco = Braco("tratamento", (_e("aberto", "2"), _e("clicado", "2")), histograma)
    achado = detecta_ctor_anomalo(braco, piso_ctor=PISO_CTOR)
    assert achado is not None
    assert dict(achado.evidencia) == {nome: int(n.valor or 0) for nome, n in histograma}


def test_ctor_sem_impressao_nao_gera_achado() -> None:
    braco = Braco("tratamento", (_e("clicado", "1"),))  # sem etapa "aberto"
    assert detecta_ctor_anomalo(braco, piso_ctor=PISO_CTOR) is None


def test_ctor_sem_clique_nao_gera_achado() -> None:
    braco = Braco("tratamento", (_e("aberto", "5"),))  # sem etapa "clicado" -> 0/5
    assert detecta_ctor_anomalo(braco, piso_ctor=PISO_CTOR) is None


def test_ctor_com_latencia_ausente_nao_roda_mesmo_com_ctor_alto() -> None:
    """[ausente] (digest arquivado antes deste campo existir, ou Braco sem
    dado algum -- default de Braco): detector nao executa, nem tenta
    tratar como histograma vazio. CTOR aqui seria 1.0, bem acima do piso
    -- se o detector rodasse mesmo assim, este teste pegaria."""
    braco = Braco(
        "tratamento", (_e("aberto", "2"), _e("clicado", "2")), _histograma_ausente(),
    )
    assert detecta_ctor_anomalo(braco, piso_ctor=PISO_CTOR) is None


# --- OPTOUT alto ---------------------------------------------------------
# braco.optout e contador auxiliar (fora de funil.cadeia), agora Numero
# (C4/RF-17); "entregue" segue vindo de braco.etapas, igual a antes.


def test_optout_abaixo_do_piso_nao_gera_achado() -> None:
    braco = Braco(
        "tratamento", (_e("entregue", "20"),), optout=Numero(Decimal("1"), "medido"),
    )  # 1/20=0.05, nao > 0.05
    assert detecta_optout_alto(braco, piso_optout=PISO_OPTOUT) is None


def test_optout_acima_do_piso_gera_achado() -> None:
    braco = Braco(
        "tratamento", (_e("entregue", "10"),), optout=Numero(Decimal("2"), "medido"),
    )
    achado = detecta_optout_alto(braco, piso_optout=PISO_OPTOUT)
    assert achado is not None
    assert achado.tipo == "optout_alto"
    assert achado.evidencia == {"optouts": 2, "entregues": 10}


def test_optout_sem_entrega_nao_gera_achado() -> None:
    braco = Braco("tratamento", (), optout=Numero(Decimal("1"), "medido"))  # sem "entregue"
    assert detecta_optout_alto(braco, piso_optout=PISO_OPTOUT) is None


def test_optout_zero_medido_e_optout_ausente_dao_saidas_diferentes() -> None:
    """Zero medido (contamos, achamos zero optouts -- fato confiavel) e
    ausente (Braco sem esse dado -- default; ou digest arquivado antes do
    campo existir) tem que se comportar diferente: os dois nao geram
    achado (nao ha optout acima de piso em nenhum dos casos), mas so o
    primeiro RODOU de verdade. A distincao observavel vive no rotulo, nao
    no retorno do detector -- por isso o teste inspeciona os dois lados."""
    entregue = _e("entregue", "10")

    braco_medido = Braco("tratamento", (entregue,), optout=Numero(Decimal("0"), "medido"))
    braco_ausente = Braco("tratamento", (entregue,))  # default: optout [ausente]

    assert braco_medido.optout.rotulo == "medido"
    assert braco_medido.optout.valor == Decimal("0")
    assert braco_ausente.optout.rotulo == "ausente"
    assert braco_ausente.optout.valor is None

    assert detecta_optout_alto(braco_medido, piso_optout=PISO_OPTOUT) is None
    assert detecta_optout_alto(braco_ausente, piso_optout=PISO_OPTOUT) is None
