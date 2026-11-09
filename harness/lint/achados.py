"""Achados sobre dado existente (B3). Anexam evidencia, NAO filtram.

O codigo detecta e anexa; o modelo explica. Filtrar dado dentro do agregador
sem decisao explicita e versionada e antipadrao -- ver B3.1.

Le do Digest, nunca de linha bruta -- histograma de latencia e contador de
optout ja vem agregados por monta_digest (harness/ingest/agrega.py), a
mesma agregacao que produz os etapas de funil. Antes deste commit, estas
duas funcoes recebiam `linhas` (Iterable[dict[str,str]]) e recalculavam
tudo por conta propria; o problema nao era so duplicar trabalho -- era que
Z0 (a fonte das linhas) tem TTL de 30 dias, e o Digest reconstruido do
disco depois disso nao tinha para onde essas funcoes olharem. Agora
olham para o mesmo Digest que os gates C ja usam.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from harness.contracts import Braco, EtapaFunilNome, Numero
from harness.pisos import Piso


@dataclass(frozen=True)
class Achado:
    tipo: str
    resumo: str
    evidencia: Mapping[str, int]


def _valor_etapa(braco: Braco, nome: EtapaFunilNome) -> Decimal | None:
    for etapa in braco.etapas:
        if etapa.nome == nome:
            return etapa.volume.valor
    return None


def _evidencia_de_latencia(
    latencia: tuple[tuple[str, Numero], ...],
) -> dict[str, int]:
    evidencia: dict[str, int] = {}
    for nome, numero in latencia:
        if numero.valor is None:
            continue
        evidencia[nome] = int(numero.valor)
    return evidencia


def detecta_ctor_anomalo(braco: Braco, *, piso_ctor: Piso) -> Achado | None:
    """CLICK / IMPRESSION acima do piso. Evidencia e o histograma de
    latencia entrega->clique que monta_digest ja calculou (braco.
    latencia_entrega_clique) -- 94,5% de CTOR e assinatura plausivel de
    bot corporativo, mas e hipotese, nao fato (ver B3.1 no prompt).

    [ausente] (digest arquivado antes deste campo existir) -- detector nao
    roda, nao tenta inferir nem tratar como zero.
    """
    if any(numero.rotulo == "ausente" for _, numero in braco.latencia_entrega_clique):
        return None

    impressoes = _valor_etapa(braco, "aberto")
    if impressoes is None:
        return None

    cliques = _valor_etapa(braco, "clicado")
    if cliques is None:
        cliques = Decimal(0)

    ctor = cliques / impressoes
    if ctor <= piso_ctor.valor:
        return None

    return Achado(
        tipo="ctor_anomalo",
        resumo=(
            f"CLICK/IMPRESSION={ctor} acima do piso {piso_ctor.valor} "
            f"(origem={piso_ctor.origem})"
        ),
        evidencia=_evidencia_de_latencia(braco.latencia_entrega_clique),
    )


def detecta_optout_alto(braco: Braco, *, piso_optout: Piso) -> Achado | None:
    """OPTOUT / ENTREGUE acima do piso -- saude de regua.

    piso_optout nao tem default em harness.pisos: o prompt nao deu esse
    numero (a confirmar). Parametro obrigatorio, sem fallback no codigo.

    [ausente] (digest arquivado antes deste campo existir) -- detector nao
    roda, nao tenta inferir nem tratar como zero.
    """
    if braco.optout.rotulo == "ausente":
        return None
    valor_optout = braco.optout.valor
    if valor_optout is None:
        return None

    entregues = _valor_etapa(braco, "entregue")
    if entregues is None:
        return None

    taxa = valor_optout / entregues
    if taxa <= piso_optout.valor:
        return None

    return Achado(
        tipo="optout_alto",
        resumo=(
            f"OPTOUT/ENTREGUE={taxa} acima do piso {piso_optout.valor} "
            f"(origem={piso_optout.origem})"
        ),
        evidencia={"optouts": int(valor_optout), "entregues": int(entregues)},
    )
