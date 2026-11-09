from decimal import Decimal

from harness.contracts import Braco, Digest, EtapaFunil, Numero
from harness.lint.c3 import c3_entrega, entrega_comparavel
from harness.pisos import Piso

INI, FIM = "2026-07-01T00:00:00Z", "2026-07-08T00:00:00Z"


def _digest(*etapas: EtapaFunil) -> Digest:
    return Digest(
        casa="brand_a", fase="leitura", universo="csv", campanha_id="9000001",
        janela_inicio=INI, janela_fim=FIM,
        hipotese="h", contexto="", bracos=(Braco("tratamento", etapas),),
        proveniencia={"fonte": "teste"},
    )


def _e(nome: str, v: str) -> EtapaFunil:
    return EtapaFunil(nome, Numero(Decimal(v), "medido"))  # type: ignore[arg-type]


def test_entrega_baixa_e_lint_verde_com_achado() -> None:
    r = c3_entrega(_digest(_e("enviado", "7268"), _e("entregue", "4796")))
    assert r.veredito == "verde"
    assert r.achados and r.achados[0].gate == "C3"
    assert r.piso_usado.origem == "default_nao_validado"


def test_entrega_acima_do_piso_nao_gera_achado() -> None:
    r = c3_entrega(_digest(_e("enviado", "1000"), _e("entregue", "950")))
    assert r.veredito == "verde"
    assert r.achados == ()


def test_sem_etapa_entregue_e_indeterminado() -> None:
    r = c3_entrega(_digest(_e("enviado", "1000")))
    assert r.veredito == "indeterminado"
    assert r.achados == ()


def test_entregue_maior_que_enviado_e_vermelho() -> None:
    r = c3_entrega(_digest(_e("enviado", "100"), _e("entregue", "150")))
    assert r.veredito == "vermelho"


def test_piso_e_injetado_nao_carregado_pelo_gate() -> None:
    d = _digest(_e("enviado", "1000"), _e("entregue", "600"))
    assert c3_entrega(d, Piso(Decimal("0.85"), "crm_md")).achados
    assert c3_entrega(d, Piso(Decimal("0.50"), "crm_md")).achados == ()


def test_avalia_por_braco_nao_somado() -> None:
    tratamento = Braco("tratamento", (_e("enviado", "1000"), _e("entregue", "950")))
    comparacao = Braco("comparacao", (_e("enviado", "1000"), _e("entregue", "400")))
    d = Digest(
        casa="brand_a", fase="leitura", universo="csv", campanha_id="x",
        janela_inicio=INI, janela_fim=FIM, hipotese="h", contexto="",
        bracos=(tratamento, comparacao),
        proveniencia={"fonte": "teste"},
    )
    r = c3_entrega(d, Piso(Decimal("0.85"), "crm_md"))
    assert len(r.achados) == 1
    assert r.achados[0].braco == "comparacao"


def test_bracos_ambos_acima_do_piso_mas_incomparaveis() -> None:
    """95% vs 60%: nenhum reprova o piso, e o contraste esta contaminado."""
    tratamento = Braco("tratamento", (_e("enviado", "1000"), _e("entregue", "950")))
    comparacao = Braco("comparacao", (_e("enviado", "1000"), _e("entregue", "600")))
    d = Digest(
        casa="brand_a", fase="leitura", universo="csv", campanha_id="x",
        janela_inicio=INI, janela_fim=FIM, hipotese="h", contexto="",
        bracos=(tratamento, comparacao),
        proveniencia={"fonte": "teste"},
    )
    r = c3_entrega(d, Piso(Decimal("0.50"), "crm_md"))
    assert r.achados == (), "por braco, nenhum reprova -- confirma a lacuna"


def test_entrega_diferencial_entre_bracos() -> None:
    tratamento = Braco("tratamento", (_e("enviado", "1000"), _e("entregue", "950")))
    comparacao = Braco("comparacao", (_e("enviado", "1000"), _e("entregue", "600")))
    d = Digest(
        casa="brand_a", fase="leitura", universo="csv", campanha_id="x",
        janela_inicio=INI, janela_fim=FIM, hipotese="h", contexto="",
        bracos=(tratamento, comparacao),
        proveniencia={"fonte": "teste"},
    )
    r = entrega_comparavel(d, Piso(Decimal("0.05"), "crm_md"))
    assert r.achados, "35pp de diferenca contamina o contraste"
    assert r.veredito == "verde"


def test_entrega_semelhante_entre_bracos_nao_gera_achado() -> None:
    a = Braco("tratamento", (_e("enviado", "1000"), _e("entregue", "950")))
    b = Braco("comparacao", (_e("enviado", "1000"), _e("entregue", "940")))
    d = Digest(
        casa="brand_a", fase="leitura", universo="csv", campanha_id="x",
        janela_inicio=INI, janela_fim=FIM, hipotese="h", contexto="",
        bracos=(a, b),
        proveniencia={"fonte": "teste"},
    )
    assert entrega_comparavel(d, Piso(Decimal("0.05"), "crm_md")).achados == ()


def test_braco_unico_e_indeterminado_para_comparabilidade() -> None:
    d = _digest(_e("enviado", "1000"), _e("entregue", "600"))
    assert entrega_comparavel(d, Piso(Decimal("0.05"), "crm_md")).veredito == "indeterminado"
