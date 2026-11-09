from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Literal

from harness.casas import casas_validas

Rotulo = Literal["medido", "estimado", "ausente"]
EtapaFunilNome = Literal["enviado", "entregue", "aberto", "clicado", "convertido"]
BracoNome = Literal["holdout", "comparacao", "tratamento"]

# Baldes fixos e declarados no codigo -- configuravel viraria piso nao
# decidido (mesma razao de harness.pisos nao aceitar valor arbitrario sem
# lineage). Justificativa pela hipotese de bot corporativo (clique quase
# simultaneo a entrega -- CRM.md B3), nao por estetica: "<=0s"/"1-60s"
# isolam o que e fisica ou humanamente implausivel (ninguem le, decide e
# clica em ate um minuto de receber a mensagem); "61-3600s" ainda e rapido
# mas plausivel para humano atento; "3601-86400s" e o grosso do
# engajamento humano; ">86400s" e cauda tardia. Mesmos 5 baldes que ja
# existiam isolados em achados.py antes deste commit -- so mudam de dono
# (a agregacao em monta_digest), nao de forma.
BucketLatencia = Literal["<=0s", "1-60s", "61-3600s", "3601-86400s", ">86400s"]
ORDEM_BUCKETS_LATENCIA: tuple[BucketLatencia, ...] = (
    "<=0s", "1-60s", "61-3600s", "3601-86400s", ">86400s",
)

# Como o holdout foi construido (B0.1). CSV = base congelada, sem porta de
# entrada na janela. state/behaviour = segmento vivo -- quem sai no meio da
# janela quebra o denominador dos dois bracos. Taxonomia fechada por natureza.
Universo = Literal["state", "behaviour", "csv"]

# preflight = plano (SpecCampanha), leitura = dado (Digest), risco = veredito
# de um risk squad (VeredictoRisco, E23) -- fora do funil causal, mas mesma
# obrigatoriedade de rotulo explicito (B0.2): sem isso um verde antigo e
# ambiguo entre as tres formas.
Fase = Literal["preflight", "leitura", "risco"]


@dataclass(frozen=True)
class Numero:
    valor: Decimal | None
    rotulo: Rotulo

    def __post_init__(self) -> None:
        if self.rotulo == "ausente" and self.valor is not None:
            raise ValueError("rotulo 'ausente' exige valor None")
        if self.rotulo != "ausente" and self.valor is None:
            raise ValueError(f"rotulo {self.rotulo!r} exige valor")


@dataclass(frozen=True)
class EtapaFunil:
    nome: EtapaFunilNome
    volume: Numero


def _histograma_ausente() -> tuple[tuple[BucketLatencia, Numero], ...]:
    return tuple((nome, Numero(None, "ausente")) for nome in ORDEM_BUCKETS_LATENCIA)


@dataclass(frozen=True)
class Braco:
    nome: BracoNome
    etapas: tuple[EtapaFunil, ...]
    # Agregados derivados de Z0 que so existiam em linha bruta (achados.py,
    # antes deste commit) -- Z0 morre em 30 dias, agregacao dele tem que
    # viver em Z1 (Digest). Ambos POR BRACO, ambos Numero (C4/RF-17: todo
    # numero do projeto e Decimal+rotulo) e ambos tuple (toda colecao em
    # dataclass frozen e tuple -- com isso Braco volta a ser hashavel de
    # verdade: um dict, mesmo dentro de frozen dataclass, ainda e mutavel
    # em lugar). optout e contador auxiliar, NAO etapa de funil -- ver
    # EtapaFunilNome/vocab.CODIGO_OPTOUT: entrar em etapas quebraria a
    # monotonicidade que C5 vai checar. Default de ambos e [ausente]: um
    # Braco construido sem esses dados nao "mediu zero", so nao informou --
    # mesmo raciocinio de le_digest para digest arquivado antes deste campo.
    latencia_entrega_clique: tuple[tuple[BucketLatencia, Numero], ...] = field(
        default_factory=_histograma_ausente
    )
    optout: Numero = field(default_factory=lambda: Numero(None, "ausente"))

    def __post_init__(self) -> None:
        vistos = [e.nome for e in self.etapas]
        if len(vistos) != len(set(vistos)):
            raise ValueError("etapa duplicada no braco")
        baldes = tuple(nome for nome, _ in self.latencia_entrega_clique)
        if baldes != ORDEM_BUCKETS_LATENCIA:
            raise ValueError(
                f"latencia_entrega_clique precisa ter exatamente os baldes "
                f"{ORDEM_BUCKETS_LATENCIA} nessa ordem, recebeu {baldes}"
            )


# str, nao mais Literal (B0.3): terceiro operador e linha em config/casas.yaml,
# zero linha de codigo. Validado em tempo de construcao contra o registry.
Casa = str


@dataclass(frozen=True)
class Digest:
    casa: Casa
    fase: Fase
    universo: Universo
    campanha_id: str
    janela_inicio: str
    janela_fim: str
    hipotese: str
    contexto: str
    bracos: tuple[Braco, ...]
    # De onde cada numero veio: fonte (csv/postgres), arquivo ou query, hash
    # (E2/E3, E6, CRM.md). O digest e arquivado permanentemente; sem isso a
    # decisao vira numero sem origem quando a fonte expira (CSV tem TTL).
    proveniencia: dict[str, str]

    def __post_init__(self) -> None:
        if self.casa not in casas_validas():
            raise ValueError(f"casa desconhecida: {self.casa!r}")
        if self.fase != "leitura":
            raise ValueError("Digest exige fase == 'leitura' (B0.2)")
        if not self.bracos:
            raise ValueError("digest exige ao menos um braco")
        if not self.hipotese.strip():
            raise ValueError("hipotese ex-ante obrigatoria (C7)")
        if "fonte" not in self.proveniencia:
            raise ValueError("proveniencia exige a chave 'fonte' (E6)")
        nomes = [b.nome for b in self.bracos]
        if len(nomes) != len(set(nomes)):
            raise ValueError("braco duplicado no digest")
        if self.janela_fim <= self.janela_inicio:
            raise ValueError("janela_fim deve ser maior que janela_inicio")

    def como_dict(self) -> dict[str, object]:
        return asdict(self)
