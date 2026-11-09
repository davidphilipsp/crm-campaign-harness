"""Z0 -> Z1: agrega linhas de j_communication em um Digest.

Conta USUARIOS DISTINTOS por etapa, nao eventos. Duas razoes:
- retentativa tecnica duplica communication_id (planejamento.md §9, armadilha 5)
- a pergunta do funil e "quantas pessoas", nao "quantos eventos"

Tambem agrega, por braco, o que so existia em linha bruta: histograma de
latencia entrega->clique e contador de optout (ambos consumidos por
harness.lint.achados). Z0 tem TTL de 30 dias; a agregacao derivada dele
precisa viver em Z1 (Digest), senao morre com o CSV.
"""

from datetime import datetime
from decimal import Decimal

from harness.contracts import (
    ORDEM_BUCKETS_LATENCIA,
    Braco,
    BracoNome,
    Casa,
    Digest,
    EtapaFunil,
    Numero,
    Universo,
)
from harness.ingest.fonte import FonteZ0
from harness.ingest.reader import iso_utc
from harness.ingest.vocab import CODIGO_OPTOUT, ORDEM_FUNIL, etapa_de_fact_type


def _bucket(delta_s: int) -> str:
    if delta_s <= 0:
        return "<=0s"
    if delta_s <= 60:
        return "1-60s"
    if delta_s <= 3600:
        return "61-3600s"
    if delta_s <= 86400:
        return "3601-86400s"
    return ">86400s"


def _delta_segundos(evento_anterior: str, evento_posterior: str) -> int:
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    t0 = datetime.strptime(iso_utc(evento_anterior), fmt)
    t1 = datetime.strptime(iso_utc(evento_posterior), fmt)
    return int((t1 - t0).total_seconds())


def monta_digest(
    fonte: FonteZ0,
    *,
    braco: BracoNome,
    casa: Casa,
    universo: Universo,
    campanha_id: str,
    janela_inicio: str,
    janela_fim: str,
    hipotese: str,
    contexto: str,
) -> Digest:
    vistos: set[tuple[str, str]] = set()
    usuarios: dict[str, set[str]] = {}
    usuarios_optout: set[str] = set()
    tempo_entrega: dict[str, str] = {}
    tempo_clique: dict[str, str] = {}
    n = 0

    for linha in fonte.linhas():
        n += 1
        cid = linha["communication_id"]
        ft = linha["fact_type_id"]
        if not ft:
            continue
        chave = (cid, ft)
        if chave in vistos:
            continue
        vistos.add(chave)

        codigo = int(ft)
        if codigo == CODIGO_OPTOUT:
            usuarios_optout.add(linha["user_ext_id"])

        etapa = etapa_de_fact_type(codigo)
        if etapa == "entregue" and "event_time" in linha:
            tempo_entrega[cid] = linha["event_time"]
        elif etapa == "clicado" and "event_time" in linha:
            tempo_clique[cid] = linha["event_time"]

        if etapa is None:
            continue
        usuarios.setdefault(etapa, set()).add(linha["user_ext_id"])

    if n == 0:
        raise ValueError("nenhuma linha para agregar")

    etapas = tuple(
        EtapaFunil(nome, Numero(Decimal(len(usuarios[nome])), "medido"))
        for nome in ORDEM_FUNIL
        if nome in usuarios
    )

    # [medido] sempre -- a fonte foi lida agora mesmo, nunca [estimado].
    # Ordem fixa (ORDEM_BUCKETS_LATENCIA), nao a ordem de insercao de um dict.
    contagem_latencia: dict[str, int] = dict.fromkeys(ORDEM_BUCKETS_LATENCIA, 0)
    for cid in tempo_clique.keys() & tempo_entrega.keys():
        delta = _delta_segundos(tempo_entrega[cid], tempo_clique[cid])
        contagem_latencia[_bucket(delta)] += 1
    latencia = tuple(
        (nome, Numero(Decimal(contagem_latencia[nome]), "medido"))
        for nome in ORDEM_BUCKETS_LATENCIA
    )

    return Digest(
        casa=casa,
        fase="leitura",  # agrega so produz digest de leitura; preflight produz o de spec
        universo=universo,
        campanha_id=campanha_id,
        janela_inicio=janela_inicio,
        janela_fim=janela_fim,
        hipotese=hipotese,
        contexto=contexto,
        bracos=(
            Braco(
                braco, etapas, latencia,
                Numero(Decimal(len(usuarios_optout)), "medido"),
            ),
        ),
        proveniencia=fonte.proveniencia(),
    )
