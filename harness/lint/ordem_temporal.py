"""C6-ordem: ordem temporal impossivel entre entrega e clique.

Clique carimbado em ou antes da entrega (balde "<=0s" do histograma de
latencia, harness.contracts.Braco.latencia_entrega_clique) e dado
estruturalmente impossivel -- mesma classe de erro que c3_entrega trata
para entregue > enviado (Digest quebrado, nao performance ruim), so que
aqui a evidencia ja vem agregada por braco por monta_digest. Antes deste
gate, isso so aparecia dentro da evidencia do detector ctor_anomalo, e so
quando o CTOR passava de um piso de negocio -- dado impossivel nao pode
depender de piso pra ser visto.

Funcao pura: sem I/O, sem relogio, sem piso -- ordem impossivel nao e
questao de "quanto e aceitavel", e sim de dado estruturalmente errado.
Avalia POR BRACO, como c3_entrega: um braco contaminado nao pode
desaparecer numa soma ou numa media com outro braco limpo.

Filiacao com C6: inferida pelo nome, nao formal -- ROSTER
(harness/lint/runner.py) e uma tupla achatada, sem campo de parentesco
entre entradas (mesma situacao de "C1-b" com "C1"). "C6-ordem" e so o
identificador; nao reduz gates_ausentes -- "C6" propriamente dito
(coerencia de braco entre reguas FTD->STD->TTD, CRM.md P7) continua sem
implementacao nenhuma.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from harness.contracts import Braco, Digest

Veredito = Literal["verde", "vermelho", "indeterminado"]

_PRECEDENCIA: dict[Veredito, int] = {"verde": 0, "indeterminado": 1, "vermelho": 2}


@dataclass(frozen=True)
class Achado:
    gate: str
    braco: str
    resumo: str
    evidencia: Mapping[str, int]


@dataclass(frozen=True)
class Resultado:
    veredito: Veredito
    achados: tuple[Achado, ...]


def _avalia_braco(braco: Braco) -> tuple[Veredito, int]:
    """[ausente] (digest arquivado antes deste campo existir, ou Braco sem
    dado algum) -- indeterminado, nunca verde: sem histograma medido, nao
    ha base pra afirmar que a ordem e valida. A contagem so importa
    quando o veredito e vermelho; nos outros dois casos vem 0."""
    numero = dict(braco.latencia_entrega_clique)["<=0s"]
    if numero.rotulo == "ausente":
        return "indeterminado", 0
    valor = numero.valor if numero.valor is not None else Decimal(0)
    return ("vermelho" if valor > 0 else "verde"), int(valor)


def avalia_ordem_temporal(digest: Digest) -> Resultado:
    """C6-ordem. Vermelho vence indeterminado, que vence verde -- mesma
    precedencia de harness.lint.runner._agrega, aqui entre bracos do
    mesmo gate em vez de entre gates diferentes."""
    achados: list[Achado] = []
    pior: Veredito = "verde"
    for braco in digest.bracos:
        veredito_braco, contagem = _avalia_braco(braco)
        if _PRECEDENCIA[veredito_braco] > _PRECEDENCIA[pior]:
            pior = veredito_braco
        if veredito_braco == "vermelho":
            achados.append(
                Achado(
                    gate="C6-ordem",
                    braco=braco.nome,
                    resumo=(
                        f"{contagem} clique(s) carimbado(s) em ou antes da entrega "
                        f"no braco {braco.nome!r} -- ordem temporal impossivel"
                    ),
                    evidencia={"<=0s": contagem},
                )
            )
    return Resultado(veredito=pior, achados=tuple(achados))
