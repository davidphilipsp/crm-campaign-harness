"""C2/C3 -- entrega vs piso e comparabilidade entre bracos (P3/B1).

Mesma logica de B3 (achados.py): o piso so anexa achado, nunca filtra ou
bloqueia -- entrega abaixo do piso ainda e "verde" porque o dado em si e
legivel, so a evidencia fica anexada para o modelo explicar. "vermelho" e
reservado para dado estruturalmente invalido (entregue > enviado), nao para
performance ruim.

C3 (`c3_entrega`) e avaliado por braco, nunca somado entre bracos: somar
mascara justamente o braco que esta ruim. C2 (`entrega_comparavel`) e
complementar -- dois bracos podem passar o piso individual de C3 e ainda
assim contaminar o contraste se a entrega diverge muito entre eles. Piso e
sempre injetado pelo caller; este modulo so faz I/O (`carrega_piso`) quando
nenhum Piso e passado, mesmo default usado no resto do harness (B1).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from harness.contracts import Braco, Digest, EtapaFunilNome
from harness.pisos import Piso, carrega_piso

Veredito = Literal["verde", "vermelho", "indeterminado"]


@dataclass(frozen=True)
class Achado:
    gate: str
    braco: str
    resumo: str
    evidencia: Mapping[str, Decimal]


@dataclass(frozen=True)
class ResultadoC3:
    veredito: Veredito
    achados: tuple[Achado, ...]
    piso_usado: Piso


@dataclass(frozen=True)
class AchadoComparabilidade:
    gate: str
    bracos: tuple[str, str]
    resumo: str
    evidencia: Mapping[str, Decimal]


@dataclass(frozen=True)
class ResultadoComparabilidade:
    veredito: Veredito
    achados: tuple[AchadoComparabilidade, ...]
    piso_usado: Piso


@dataclass(frozen=True)
class _BracoAvaliado:
    nome: str
    enviado: Decimal
    entregue: Decimal
    entrega: Decimal


def _valor_etapa(braco: Braco, nome: EtapaFunilNome) -> Decimal | None:
    for etapa in braco.etapas:
        if etapa.nome == nome:
            return etapa.volume.valor
    return None


def _avaliaveis(digest: Digest) -> list[_BracoAvaliado]:
    """Bracos com enviado/entregue medidos e enviado > 0 -- os demais ficam
    de fora e viram 'indeterminado' no caller quando a lista fica vazia
    (ou curta demais para C2, que precisa de pelo menos dois bracos).
    """
    avaliados: list[_BracoAvaliado] = []
    for braco in digest.bracos:
        enviado = _valor_etapa(braco, "enviado")
        entregue = _valor_etapa(braco, "entregue")
        if enviado is None or entregue is None or enviado == 0:
            continue
        avaliados.append(
            _BracoAvaliado(
                nome=braco.nome,
                enviado=enviado,
                entregue=entregue,
                entrega=entregue / enviado,
            )
        )
    return avaliados


def c3_entrega(digest: Digest, piso: Piso | None = None) -> ResultadoC3:
    """C3 -- ENTREGUE / ENVIADO, usuarios distintos, por braco."""
    piso_efetivo = piso if piso is not None else carrega_piso("C3_ENTREGA_MINIMA")

    avaliaveis = _avaliaveis(digest)
    if not avaliaveis:
        return ResultadoC3(veredito="indeterminado", achados=(), piso_usado=piso_efetivo)

    if any(b.entregue > b.enviado for b in avaliaveis):
        return ResultadoC3(veredito="vermelho", achados=(), piso_usado=piso_efetivo)

    achados = tuple(
        Achado(
            gate="C3",
            braco=b.nome,
            resumo=(
                f"entrega={b.entrega} abaixo do piso {piso_efetivo.valor} "
                f"(origem={piso_efetivo.origem})"
            ),
            evidencia={"enviado": b.enviado, "entregue": b.entregue},
        )
        for b in avaliaveis
        if b.entrega < piso_efetivo.valor
    )
    return ResultadoC3(veredito="verde", achados=achados, piso_usado=piso_efetivo)


def entrega_comparavel(digest: Digest, piso: Piso | None = None) -> ResultadoComparabilidade:
    """C2 -- desvio de entrega entre bracos (C2_DESVIO_MAX_BRACOS).

    Regua, base ou timing distintos entre bracos mudam o denominador efetivo
    de cada lado; quando o desvio entre o braco de maior e o de menor entrega
    passa do piso, o contraste deixa de ser like-for-like mesmo que cada
    braco, isolado, tenha passado em C3.
    """
    piso_efetivo = piso if piso is not None else carrega_piso("C2_DESVIO_MAX_BRACOS")

    avaliaveis = _avaliaveis(digest)
    if len(avaliaveis) < 2:
        return ResultadoComparabilidade(
            veredito="indeterminado", achados=(), piso_usado=piso_efetivo
        )

    maior = max(avaliaveis, key=lambda b: b.entrega)
    menor = min(avaliaveis, key=lambda b: b.entrega)
    desvio = maior.entrega - menor.entrega

    if desvio <= piso_efetivo.valor:
        return ResultadoComparabilidade(veredito="verde", achados=(), piso_usado=piso_efetivo)

    achado = AchadoComparabilidade(
        gate="C2",
        bracos=(maior.nome, menor.nome),
        resumo=(
            f"desvio de entrega entre bracos={desvio} acima do piso "
            f"{piso_efetivo.valor} (origem={piso_efetivo.origem}): "
            f"{maior.nome}={maior.entrega} vs {menor.nome}={menor.entrega}"
        ),
        evidencia={"maior": maior.entrega, "menor": menor.entrega, "desvio": desvio},
    )
    return ResultadoComparabilidade(veredito="verde", achados=(achado,), piso_usado=piso_efetivo)
