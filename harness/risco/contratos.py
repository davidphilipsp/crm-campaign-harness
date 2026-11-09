"""Contrato de VeredictoRisco (E23, CRM.md).

O harness e orquestrador do CONTRATO, nao da analise: cada risk squad
(brand-a-risk-squad, brand-b-financial-squad) mantem total autonomia sobre como
chega ao numero -- schema proprio, SQL ad hoc, subagentes, julgamento sobre
dado inconsistente (ver os tres relatorios que originaram esta emenda).
O harness so aceita o resumo final, num formato fixo, e decide se cruza a
fronteira para o consumidor downstream. Reimplementar a analise aqui duplicaria logica
que diverge na primeira correcao de bug (mesmo argumento de E6).

VeredictoRisco nao carrega player_id nem qualquer coluna tecnica do PAM --
so agregados que o proprio squad ja calculou. cobertura_piso/cobertura_ok
sao decisao do harness (piso proprio, com lineage), nunca do squad.

cobertura_pct e Numero, nao Decimal cru (E24): testando o contrato contra
os tres relatorios reais que originaram a E23, os dois de AntiChurn nunca
calcularam esse numero -- so o de torneios. Forcar um Decimal obrigatorio
faria o squad inventar um valor (viola Art. IV) ou travaria a ingestao pra
sempre (as sessoes que produziram os relatorios ja foram encerradas, nao
da pra voltar e calcular). "ausente" e o mesmo rotulo que EtapaFunil.volume
e optout ja usam em harness/contracts.py -- cobertura_pct nunca deveria ter
sido a unica medicao do sistema sem essa saida honesta.
"""

from dataclasses import dataclass
from decimal import Decimal

from harness.casas import casas_validas
from harness.contracts import Fase, Numero
from harness.lint.contratos import AchadoUnificado
from harness.pisos import Piso
from harness.squads import squads_validos


@dataclass(frozen=True)
class SegmentoRisco:
    nome: str
    custo_total: Decimal
    unidades_ofertadas: int
    unidades_usadas: int
    taxa_aproveitamento: Decimal
    # None quando a estrutura de dado do squad nao permite isolar turnover
    # atribuido ao bonus (caso brand-b, sem tabela dedicada) -- nunca um numero
    # aproximado no lugar de uma medicao que nao existe.
    turnover_atribuido: Decimal | None = None


@dataclass(frozen=True)
class VeredictoRisco:
    fase: Fase
    casa: str
    squad: str
    acao: str
    janela_inicio: str
    janela_fim: str
    segmentos: tuple[SegmentoRisco, ...]
    cobertura_pct: Numero
    cobertura_piso: Piso
    cobertura_ok: bool
    # Achado, nunca veredito causal -- mesma logica de E4/BracoNome: os tres
    # relatorios que originaram esta emenda encontraram o grupo exposto
    # mais ativo que o controle antes da campanha em todos os casos que
    # mediram isso, e nenhum tinha holdout de verdade.
    vies_selecao: AchadoUnificado | None
    achados_governanca: tuple[AchadoUnificado, ...]
    proveniencia: dict[str, str]

    def __post_init__(self) -> None:
        if self.fase != "risco":
            raise ValueError("VeredictoRisco exige fase == 'risco' (B0.2, E23)")
        if self.casa not in casas_validas():
            raise ValueError(f"casa desconhecida: {self.casa!r}")
        if self.squad not in squads_validos():
            raise ValueError(f"squad desconhecido: {self.squad!r}")
        if not self.segmentos:
            raise ValueError("VeredictoRisco exige ao menos um segmento")
        nomes = [s.nome for s in self.segmentos]
        if len(nomes) != len(set(nomes)):
            raise ValueError("segmento duplicado no veredicto de risco")
        if self.janela_fim <= self.janela_inicio:
            raise ValueError("janela_fim deve ser maior que janela_inicio")
        if "fonte" not in self.proveniencia:
            raise ValueError("proveniencia exige a chave 'fonte' (E7)")


def avalia_cobertura(cobertura_pct: Numero, piso: Piso) -> bool:
    """C-RISCO-COBERTURA: cobertura abaixo do piso -- ou ausente -- suspende
    o veredito (cobertura_ok=False) sem descartar o resultado, mesmo padrao
    de C3: o numero (ou a ausencia dele) fica visivel, so marcado como nao
    confiavel o suficiente. Ausente nunca conta como "acima do piso" --
    silencio nao e evidencia de qualidade."""
    return cobertura_pct.valor is not None and cobertura_pct.valor >= piso.valor
