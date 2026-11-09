"""Preflight (B2): funcoes puras sobre uma SpecCampanha. SEM I/O, SEM Z0, SEM dado.

C1-C7 respondem "isso foi lido com metodo integro?" depois que a campanha ja
rodou -- tarde para agir. Preflight responde a unica pergunta que ainda da
tempo de mudar: "essa campanha vai poder ser lida?"

Pisos entram como Piso ja resolvido (harness.pisos.carrega_piso, que faz I/O)
-- este modulo nunca le arquivo.
"""

import math
import statistics
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal
from typing import Literal

from harness.casas import casas_validas
from harness.contracts import Fase, Universo
from harness.pisos import Piso

FonteConversaoControle = Literal["no_flow", "evento_atribuido", "ausente"]
Veredito = Literal["ILEGIVEL", "LIMITROFE", "OK"]

_ALTERNATIVAS_ILEGIVEL = (
    "pooling entre ciclos da mesma regua",
    "declarar comparativo desde o inicio",
)


@dataclass(frozen=True)
class SpecCampanha:
    fase: Fase
    casa: str
    universo: Universo
    regua: str
    base_estimada: int
    pct_holdout: Decimal
    conversao_esperada: Decimal
    fonte_conversao_controle: FonteConversaoControle
    max_duration_s: int
    delays_s: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.fase != "preflight":
            raise ValueError("SpecCampanha exige fase == 'preflight' (B0.2)")
        if self.casa not in casas_validas():
            raise ValueError(f"casa desconhecida: {self.casa!r}")
        if not self.regua.strip():
            raise ValueError("regua obrigatoria")
        if self.base_estimada <= 0:
            raise ValueError("base_estimada deve ser positiva")
        if not (Decimal("0") < self.pct_holdout < Decimal("1")):
            raise ValueError("pct_holdout deve estar em (0, 1)")
        if not (Decimal("0") < self.conversao_esperada < Decimal("1")):
            raise ValueError("conversao_esperada deve estar em (0, 1)")
        if self.max_duration_s <= 0:
            raise ValueError("max_duration_s deve ser positivo")
        if any(d < 0 for d in self.delays_s):
            raise ValueError("delays_s nao pode ter valor negativo")


@dataclass(frozen=True)
class VeredictoPreflight:
    check: str
    aprova: bool
    motivo: str


@dataclass(frozen=True)
class ResultadoMDE:
    n_holdout: int
    n_tratamento: int
    mde_absoluto: Decimal
    mde_relativo: Decimal
    veredito: Veredito
    piso_amostra: Piso
    piso_mde_ok: Piso
    alternativas: tuple[str, ...] = field(default=())


def _tamanhos_de_braco(spec: SpecCampanha) -> tuple[int, int]:
    n_holdout = int(
        (Decimal(spec.base_estimada) * spec.pct_holdout).to_integral_value(ROUND_DOWN)
    )
    n_tratamento = spec.base_estimada - n_holdout
    return n_holdout, n_tratamento


def _mde_absoluto(n1: int, n2: int, conversao_esperada: Decimal) -> Decimal:
    """Efeito minimo detectavel (absoluto), teste de duas proporcoes.

    alpha=0.05 (dois lados), poder=0.80. Aproximacao normal, variancia comum
    ~ p*(1-p). z's vem de NormalDist().inv_cdf() -- nunca hardcoded.
    """
    if n1 <= 0 or n2 <= 0:
        raise ValueError("tamanho de amostra por braco deve ser positivo")
    p = float(conversao_esperada)
    normal = statistics.NormalDist()
    z_alpha = normal.inv_cdf(1 - 0.05 / 2)
    z_poder = normal.inv_cdf(0.80)
    mde = (z_alpha + z_poder) * math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return Decimal(str(mde))


def avalia_mde_vs_base(
    spec: SpecCampanha, *, piso_amostra: Piso, piso_mde_ok: Piso
) -> ResultadoMDE:
    """C8 -- MDE vs base. ILEGIVEL | LIMITROFE | OK.

    piso_amostra: eventos esperados minimos por braco para o teste ser valido
    (sem default sancionado alem do que harness.pisos ja carrega). piso_mde_ok:
    teto de lift relativo minimo detectavel para aprovar como OK -- NAO tem
    default no prompt nem no repo; caller precisa resolver (a confirmar).
    """
    n_holdout, n_tratamento = _tamanhos_de_braco(spec)
    eventos_min = min(n_holdout, n_tratamento) * spec.conversao_esperada

    mde_abs = _mde_absoluto(n_holdout, n_tratamento, spec.conversao_esperada)
    mde_rel = mde_abs / spec.conversao_esperada

    if eventos_min < piso_amostra.valor:
        veredito: Veredito = "ILEGIVEL"
    elif mde_rel <= piso_mde_ok.valor:
        veredito = "OK"
    else:
        veredito = "LIMITROFE"

    return ResultadoMDE(
        n_holdout=n_holdout,
        n_tratamento=n_tratamento,
        mde_absoluto=mde_abs,
        mde_relativo=mde_rel,
        veredito=veredito,
        piso_amostra=piso_amostra,
        piso_mde_ok=piso_mde_ok,
        alternativas=_ALTERNATIVAS_ILEGIVEL if veredito == "ILEGIVEL" else (),
    )


def avalia_fonte_conversao_controle(spec: SpecCampanha) -> VeredictoPreflight:
    """C9 -- conversao marcada dentro do flow nunca alcanca o controle."""
    if spec.fonte_conversao_controle == "no_flow":
        return VeredictoPreflight(
            check="C9",
            aprova=False,
            motivo=(
                "conversao marcada por no dentro do flow: quem esta no controle "
                "nunca percorre o flow, o holdout nasce cego"
            ),
        )
    return VeredictoPreflight(check="C9", aprova=True, motivo="")


def avalia_duracao_vs_delays(spec: SpecCampanha) -> VeredictoPreflight:
    """C11 -- max_duration_s tem que cobrir a soma real dos delays do flow."""
    soma = sum(spec.delays_s)
    if spec.max_duration_s < soma:
        return VeredictoPreflight(
            check="C11",
            aprova=False,
            motivo=f"max_duration_s={spec.max_duration_s} < soma(delays_s)={soma}",
        )
    return VeredictoPreflight(check="C11", aprova=True, motivo="")
