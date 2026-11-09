#!/usr/bin/env python3
"""Gera as fixtures golden de tests/golden/ de forma deterministica.

Sem aleatoriedade sem semente, sem relogio (datetime.now proibido aqui),
sem rede -- toda linha vem de constantes declaradas neste arquivo, cada
bloco com um comentario dizendo qual ramo do harness ele exercita. Rodar
de novo produz, byte a byte, o mesmo CSV -- tests/test_gera_golden.py
prova isso comparando a saida deste gerador com o arquivo commitado.

Por que este arquivo existe: tests/golden/demo_9000001/entrada.csv, ate
este commit, tinha event_time IDENTICO nas 1423 linhas -- toda a
distribuicao de latencia entrega->clique vinha de um artefato de
construcao da fixture, nao de comportamento (ver auditoria: balde <=0s
carregava os 105 cliques inteiros, valor unico entre todos os deltas).
Nenhum user_ext_id/communication_id aqui pseudonimiza pessoa real --
sao sinteticos, numerados a partir de indice, sem origem em dado real
(diferente de tools/anonimiza_fixture.py, que so troca o ID de uma
fixture que ja existe).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
_CABECALHO = ("event_time", "user_ext_id", "fact_type_id", "communication_id")

# Sem locale: %a/%b do strftime variam por maquina (o proprio parser,
# harness/ingest/reader.py, evita isso com uma tabela igual a esta).
_DIAS_SEMANA = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MESES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# harness/ingest/vocab.py: 2 SENT, 3 IMPRESSION, 4 CLICK, 6 DELIVERED.
_FACT_SENT = "2"
_FACT_IMPRESSAO = "3"
_FACT_CLICK = "4"
_FACT_DELIVERED = "6"


def _smartico(dt: datetime) -> str:
    """Formato bruto do Smartico (harness.ingest.reader.iso_utc). Tabela
    propria em vez de strftime("%a %b") -- locale nao decide o byte."""
    return (
        f"{_DIAS_SEMANA[dt.weekday()]} {_MESES[dt.month - 1]} {dt.day:02d} {dt.year} "
        f"{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d} GMT+0"
    )


@dataclass(frozen=True)
class _Linha:
    event_time: str
    user_ext_id: str
    fact_type_id: str
    communication_id: str


def _usuario(indice: int) -> str:
    """Sintetico, numerado -- nao deriva de nenhum id_anon nem de pessoa
    real. Mesmo estilo de tools/anonimiza_fixture.py (u_NNNN), mas gerado
    do zero, nao anonimizado a partir de outra coisa."""
    return f"u_{indice:04d}"


def _cid(indice: int) -> str:
    return str(9_000_000_000 + indice)


def _gera_demo_9000001() -> list[_Linha]:
    """Fixture principal: prova o criterio de pronto do M3.

    - entrega = 660/1000 = 0.66, abaixo do piso C3_ENTREGA_MINIMA=0.85
      -> C3 verde COM achado (o caso que M3 exige ver funcionando).
    - CTOR = 180/200 = 0.90, acima do piso CTOR_MAX_ANOMALO=0.60
      -> detecta_ctor_anomalo dispara.
    - latencia entrega->clique espalhada pelos 4 baldes normais, ZERO
      em <=0s -- nada aqui tem ordem temporal impossivel.
    """
    linhas: list[_Linha] = []

    n_enviado = 1000  # SENT -- base do funil
    n_entregue = 660  # DELIVERED -- 660/1000=0.66 < piso 0.85 (C3 verde+achado)
    n_aberto = 200  # IMPRESSION -- denominador do CTOR
    n_clicado = 180  # CLICK -- 180/200=0.90 CTOR, acima do piso 0.60

    t_sent = datetime(2026, 7, 20, 8, 55, 0)
    t_delivered = datetime(2026, 7, 20, 9, 0, 0)
    # IMPRESSION: carimbo so preenche a linha -- nenhum codigo le event_time
    # de "aberto" (so "entregue" e "clicado" alimentam a latencia).
    t_impressao = datetime(2026, 7, 20, 9, 2, 0)

    for i in range(n_enviado):
        linhas.append(_Linha(_smartico(t_sent), _usuario(i), _FACT_SENT, _cid(i)))

    for i in range(n_entregue):
        linhas.append(_Linha(_smartico(t_delivered), _usuario(i), _FACT_DELIVERED, _cid(i)))

    for i in range(n_aberto):
        linhas.append(_Linha(_smartico(t_impressao), _usuario(i), _FACT_IMPRESSAO, _cid(i)))

    # CLICK, por grupo de usuario -- delta em segundos ate o clique,
    # comentado com o balde que cada grupo exercita (harness/contracts.py
    # ORDEM_BUCKETS_LATENCIA). Soma dos grupos = n_clicado = 180.
    grupos_click = (
        (0, 40, 45),  # 1-60s: clique rapido, ainda plausivel pra humano
        (40, 100, 1_800),  # 61-3600s: 30 min depois
        (100, 150, 43_200),  # 3601-86400s: 12h depois
        (150, 180, 172_800),  # >86400s: 2 dias depois
    )
    for inicio, fim, delta_s in grupos_click:
        t_click = t_delivered + timedelta(seconds=delta_s)
        for i in range(inicio, fim):
            linhas.append(_Linha(_smartico(t_click), _usuario(i), _FACT_CLICK, _cid(i)))

    assert sum(fim - inicio for inicio, fim, _ in grupos_click) == n_clicado
    return linhas


def _gera_latencia_impossivel() -> list[_Linha]:
    """Segunda fixture: existe so para o gate de ordem temporal impossivel
    do proximo commit. Gerada agora, nao consumida por nenhum teste alem
    do proprio round-trip do gerador (tests/test_gera_golden.py) -- quem
    vai afirmar sobre ela e o commit que introduzir o gate.

    Metade dos cliques carimbados ANTES/NA entrega (balde <=0s, positivo
    de proposito -- e o caso que esta fixture prova que existe); a outra
    metade em baldes normais, para nao ser so o caso quebrado.
    """
    linhas: list[_Linha] = []

    n_enviado = 100
    n_entregue = 80
    n_aberto = 50
    n_clicado = 50

    t_sent = datetime(2026, 7, 20, 8, 55, 0)
    t_delivered = datetime(2026, 7, 20, 9, 0, 0)
    t_impressao = datetime(2026, 7, 20, 9, 2, 0)

    for i in range(n_enviado):
        linhas.append(_Linha(_smartico(t_sent), _usuario(i), _FACT_SENT, _cid(i)))

    for i in range(n_entregue):
        linhas.append(_Linha(_smartico(t_delivered), _usuario(i), _FACT_DELIVERED, _cid(i)))

    for i in range(n_aberto):
        linhas.append(_Linha(_smartico(t_impressao), _usuario(i), _FACT_IMPRESSAO, _cid(i)))

    grupos_click = (
        (0, 20, -30),  # <=0s: clique 30s ANTES da entrega -- ordem impossivel
        (20, 30, 0),  # <=0s: clique no MESMO instante da entrega -- idem
        (30, 40, 45),  # 1-60s: caso normal, para a fixture nao ser so o caso quebrado
        (40, 50, 1_800),  # 61-3600s: idem
    )
    for inicio, fim, delta_s in grupos_click:
        t_click = t_delivered + timedelta(seconds=delta_s)
        for i in range(inicio, fim):
            linhas.append(_Linha(_smartico(t_click), _usuario(i), _FACT_CLICK, _cid(i)))

    assert sum(fim - inicio for inicio, fim, _ in grupos_click) == n_clicado
    return linhas


def _formata_csv(linhas: Sequence[_Linha]) -> str:
    """Pura -- sem I/O. tests/test_gera_golden.py compara isto direto
    contra o arquivo commitado, sem escrever nada em disco."""
    buffer = io.StringIO()
    escritor = csv.writer(buffer, lineterminator="\n")
    escritor.writerow(_CABECALHO)
    for linha in linhas:
        escritor.writerow(
            (linha.event_time, linha.user_ext_id, linha.fact_type_id, linha.communication_id)
        )
    return buffer.getvalue()


def _escreve(linhas: Sequence[_Linha], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(_formata_csv(linhas), encoding="utf-8")


def gera_todas(raiz: Path = _RAIZ) -> None:
    golden = raiz / "tests" / "golden"
    _escreve(_gera_demo_9000001(), golden / "demo_9000001" / "entrada.csv")
    _escreve(_gera_latencia_impossivel(), golden / "latencia_impossivel" / "entrada.csv")


def main() -> None:
    gera_todas()


if __name__ == "__main__":
    main()
