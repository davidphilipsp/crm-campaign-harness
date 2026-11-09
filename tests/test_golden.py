"""Os numeros abaixo vem de tools/gera_golden.py (_gera_demo_9000001), nao
de captura real -- a fixture antiga tinha event_time identico nas 1423
linhas (balde <=0s carregava os 105 cliques inteiros, valor unico entre
todos os deltas), sem proveniencia pra dizer se era dado ou artefato de
construcao. Cada valor aqui exercita um ramo especifico, do lado certo
de um piso especifico:

- enviado=1000, entregue=660: entrega=660/1000=0.66, ABAIXO do piso
  C3_ENTREGA_MINIMA=0.85 (harness/pisos.py) -- C3 tem que sair verde COM
  achado. Esse e o proprio criterio de pronto do M3: o gate roda, o dado
  e legivel, mas fica registrado que a entrega nao bate o piso.
- aberto=200, clicado=180: CTOR=180/200=0.90, ACIMA do piso
  CTOR_MAX_ANOMALO=0.60 -- detecta_ctor_anomalo tem que disparar.
- latencia entrega->clique: 40 cliques a 45s (balde 1-60s), 60 a 30min
  (61-3600s), 50 a 12h (3601-86400s), 30 a 2 dias (>86400s); <=0s=0 de
  proposito -- nada nesta fixture tem ordem temporal impossivel (ver
  tests/golden/latencia_impossivel/ para o caso contrario, gerado mas
  ainda sem gate/teste que o consuma). Todos [medido]: monta_digest leu a
  fonte agora, nunca marca [estimado].

Antes deste arquivo so provar FORMA (veredito, achado presente,
digest_hash) -- nenhum teste afirmava que 660/1000 sobrevive ao caminho
CSV->digest->lint. Um bug de agregacao que mudasse entrega para 0.64,
por exemplo, passaria verde sem os asserts de valor abaixo.
"""

import json
from decimal import Decimal
from pathlib import Path

from harness.contracts import Digest, Numero
from harness.digest import digest_hash
from harness.ingest.agrega import monta_digest
from harness.ingest.fonte_csv import FonteCSV
from harness.lint.c3 import c3_entrega
from harness.lint.ordem_temporal import avalia_ordem_temporal
from harness.pisos import Piso

CASO = Path(__file__).parent / "golden" / "demo_9000001"
COLS = ("user_ext_id", "fact_type_id", "communication_id")

# Relativo ao cwd (pytest roda da raiz do repo, testpaths em pyproject.toml).
# A proveniencia do digest hasheia este caminho -- absoluto quebraria o
# golden hash entre checkouts.
CAMINHO_ENTRADA = Path("tests/golden/demo_9000001/entrada.csv")


def _digest() -> Digest:
    return monta_digest(
        FonteCSV(CAMINHO_ENTRADA, colunas_esperadas=COLS),
        braco="tratamento", casa="brand_a", universo="csv",
        campanha_id="9000001",
        janela_inicio="2026-07-01T00:00:00Z", janela_fim="2026-07-28T00:00:00Z",
        hipotese="oferta converte mais que a generica", contexto="",
    )


def test_golden_reproduz_contagens_e_hash() -> None:
    esperado = json.loads((CASO / "esperado.json").read_text(encoding="utf-8"))
    d = _digest()
    obtido = {e.nome: int(e.volume.valor or 0) for e in d.bracos[0].etapas}
    assert obtido == esperado["etapas"]
    assert digest_hash(d.como_dict()) == esperado["digest_hash"]


def test_golden_da_lint_verde_com_achado_c3() -> None:
    r = c3_entrega(_digest(), Piso(Decimal("0.85"), "default_nao_validado"))
    assert r.veredito == "verde"
    assert r.achados and r.achados[0].gate == "C3"


def test_golden_da_c6_ordem_verde() -> None:
    """<=0s=0 nesta fixture (gerada de proposito sem ordem temporal
    impossivel) -- C6-ordem tem que sair verde, sem achado. Gate nao toca
    em Digest: nada aqui muda digest_hash."""
    r = avalia_ordem_temporal(_digest())
    assert r.veredito == "verde"
    assert r.achados == ()


def test_golden_etapas_batem_com_o_gerador() -> None:
    """tools/gera_golden.py: n_enviado=1000, n_entregue=660, n_aberto=200,
    n_clicado=180. So verdito/achado/hash nao pegam um bug que mude
    qualquer um destes numeros mantendo a forma -- valor exato pega."""
    d = _digest()
    etapas = {e.nome: e.volume for e in d.bracos[0].etapas}
    assert etapas["enviado"] == Numero(Decimal("1000"), "medido")
    assert etapas["entregue"] == Numero(Decimal("660"), "medido")
    assert etapas["aberto"] == Numero(Decimal("200"), "medido")
    assert etapas["clicado"] == Numero(Decimal("180"), "medido")


def test_golden_entrega_calculada_fica_do_lado_vermelho_do_piso_c3() -> None:
    """660/1000=0.66, abaixo do piso C3_ENTREGA_MINIMA=0.85 -- e o valor
    que faz C3 sair verde COM achado. Se a agregacao subisse entrega para
    0.86, por exemplo, o achado desapareceria e o criterio de pronto do
    M3 deixaria de valer, sem nenhum teste de forma notar."""
    d = _digest()
    etapas = {e.nome: e.volume for e in d.bracos[0].etapas}
    entregue, enviado = etapas["entregue"].valor, etapas["enviado"].valor
    assert entregue is not None and enviado is not None
    assert entregue / enviado == Decimal("0.66")


def test_golden_ctor_calculado_fica_do_lado_vermelho_do_piso_ctor() -> None:
    """180/200=0.90, acima do piso CTOR_MAX_ANOMALO=0.60 -- e o valor que
    faz detecta_ctor_anomalo disparar. Se a agregacao derrubasse CTOR
    para abaixo de 0.60, o achado sumiria sem teste de forma notar."""
    d = _digest()
    etapas = {e.nome: e.volume for e in d.bracos[0].etapas}
    clicado, aberto = etapas["clicado"].valor, etapas["aberto"].valor
    assert clicado is not None and aberto is not None
    assert clicado / aberto == Decimal("0.90")


def test_golden_histograma_de_latencia_exato() -> None:
    """tools/gera_golden.py, grupos_click de _gera_demo_9000001: 40 a 45s
    (1-60s), 60 a 30min (61-3600s), 50 a 12h (3601-86400s), 30 a 2 dias
    (>86400s). <=0s=0 -- nada aqui tem ordem temporal impossivel. Todos
    [medido]: monta_digest leu a fonte agora, nunca marca [estimado]."""
    d = _digest()
    histograma = dict(d.bracos[0].latencia_entrega_clique)
    assert histograma["<=0s"] == Numero(Decimal("0"), "medido")
    assert histograma["1-60s"] == Numero(Decimal("40"), "medido")
    assert histograma["61-3600s"] == Numero(Decimal("60"), "medido")
    assert histograma["3601-86400s"] == Numero(Decimal("50"), "medido")
    assert histograma[">86400s"] == Numero(Decimal("30"), "medido")
