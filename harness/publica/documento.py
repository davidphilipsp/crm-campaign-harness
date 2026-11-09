"""P1: monta o documento do contrato harness -> consumidor downstream.

Funcao pura -- sem I/O, sem rede, sem disco. VERSAO 1 espelhava exatamente
references/consumer-interface.md; VERSAO 2 (E23) acrescentou
"riscos"; VERSAO 3 (E24) muda a forma de cobertura_pct dentro de "riscos"
(Decimal cru -> Numero, para ter um rotulo "ausente" honesto) -- ver
references/consumer-interface.md. Mudanca de forma sobe a
versao, nunca remenda a anterior (documento_v1/esperado.json e
documento_v2/esperado.json ficam orfaos, congelados como registro
historico, mesmo raciocinio de B0 em CRM.md).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from harness.contracts import Braco, EtapaFunil, Numero, Universo
from harness.lint.achados import Achado as AchadoLint
from harness.lint.c3 import (
    Achado as AchadoC3,
)
from harness.lint.c3 import (
    AchadoComparabilidade,
    ResultadoC3,
    ResultadoComparabilidade,
)
from harness.lint.contratos import AchadoUnificado
from harness.pisos import Piso
from harness.preflight import ResultadoMDE, VeredictoPreflight
from harness.risco.contratos import SegmentoRisco

VERSAO = 3


@dataclass(frozen=True)
class ResultadoPreflight:
    casa: str
    universo: Universo
    regua: str
    base_estimada: int
    pct_holdout: Decimal
    conversao_esperada: Decimal
    c8: ResultadoMDE | None = None
    c9: VeredictoPreflight | None = None
    c11: VeredictoPreflight | None = None


@dataclass(frozen=True)
class ResultadoRisco:
    """Boundary contract proprio (E23), decoupled de VeredictoRisco (harness/
    risco/contratos.py) do mesmo jeito que ResultadoLeitura e decoupled de
    Digest: sem `proveniencia` (interno, nunca publicado -- mesma omissao
    que ResultadoLeitura ja faz com o `proveniencia` de Digest). Reusa
    SegmentoRisco/AchadoUnificado diretamente -- so os tipos de fronteira
    (raiz) sao redefinidos aqui, os tipos-folha nao (mesmo padrao de Braco/
    ResultadoC3, importados sem redefinicao)."""

    casa: str
    squad: str
    acao: str
    janela_inicio: str
    janela_fim: str
    segmentos: tuple[SegmentoRisco, ...]
    cobertura_pct: Numero
    cobertura_piso: Piso
    cobertura_ok: bool
    vies_selecao: AchadoUnificado | None = None
    achados_governanca: tuple[AchadoUnificado, ...] = field(default=())


@dataclass(frozen=True)
class ResultadoLeitura:
    casa: str
    universo: Universo
    campanha_id: str
    janela_inicio: str
    janela_fim: str
    hipotese: str
    contexto: str
    digest_hash: str
    bracos: tuple[Braco, ...]
    c3: ResultadoC3 | None = None
    c2: ResultadoComparabilidade | None = None
    achados: tuple[AchadoLint, ...] = field(default=())


def monta_documento(
    preflights: tuple[ResultadoPreflight, ...],
    leituras: tuple[ResultadoLeitura, ...],
    *,
    gerado_em: str,
    harness_commit: str,
    riscos: tuple[ResultadoRisco, ...] = (),
) -> dict[str, object]:
    return {
        "versao": VERSAO,
        "gerado_em": gerado_em,
        "harness_commit": harness_commit,
        "preflights": [_preflight_dict(p) for p in preflights],
        "leituras": [_leitura_dict(leitura) for leitura in leituras],
        "riscos": [_risco_dict(r) for r in riscos],
    }


def piso_dict(p: Piso) -> dict[str, object]:
    return {"valor": str(p.valor), "origem": p.origem}


def c8_dict(r: ResultadoMDE) -> dict[str, object]:
    return {
        "veredito": r.veredito,
        "n_holdout": r.n_holdout,
        "n_tratamento": r.n_tratamento,
        "mde_absoluto": str(r.mde_absoluto),
        "mde_relativo": str(r.mde_relativo),
        "piso_amostra": piso_dict(r.piso_amostra),
        "piso_mde_ok": piso_dict(r.piso_mde_ok),
        "alternativas": list(r.alternativas),
    }


def veredicto_preflight_dict(v: VeredictoPreflight) -> dict[str, object]:
    return {"check": v.check, "aprova": v.aprova, "motivo": v.motivo}


def _preflight_dict(p: ResultadoPreflight) -> dict[str, object]:
    return {
        "fase": "preflight",
        "casa": p.casa,
        "regua": p.regua,
        "universo": p.universo,
        "base_estimada": p.base_estimada,
        "pct_holdout": str(p.pct_holdout),
        "conversao_esperada": str(p.conversao_esperada),
        "c8": c8_dict(p.c8) if p.c8 is not None else None,
        "c9": veredicto_preflight_dict(p.c9) if p.c9 is not None else None,
        "c11": veredicto_preflight_dict(p.c11) if p.c11 is not None else None,
    }


def _numero_dict(n: Numero) -> dict[str, object]:
    return {"valor": str(n.valor) if n.valor is not None else None, "rotulo": n.rotulo}


def _etapa_dict(e: EtapaFunil) -> dict[str, object]:
    return {"nome": e.nome, **_numero_dict(e.volume)}


def _braco_dict(b: Braco) -> dict[str, object]:
    return {"nome": b.nome, "etapas": [_etapa_dict(e) for e in b.etapas]}


def evidencia_decimal_dict(evidencia: Mapping[str, Decimal]) -> dict[str, str]:
    return {chave: str(valor) for chave, valor in evidencia.items()}


def _achado_c3_dict(a: AchadoC3) -> dict[str, object]:
    return {
        "gate": a.gate,
        "braco": a.braco,
        "resumo": a.resumo,
        "evidencia": evidencia_decimal_dict(a.evidencia),
    }


def c3_dict(r: ResultadoC3) -> dict[str, object]:
    return {
        "veredito": r.veredito,
        "piso_usado": piso_dict(r.piso_usado),
        "achados": [_achado_c3_dict(a) for a in r.achados],
    }


def achado_comparabilidade_dict(a: AchadoComparabilidade) -> dict[str, object]:
    return {
        "gate": a.gate,
        "bracos": list(a.bracos),
        "resumo": a.resumo,
        "evidencia": evidencia_decimal_dict(a.evidencia),
    }


def c2_dict(r: ResultadoComparabilidade) -> dict[str, object]:
    return {
        "veredito": r.veredito,
        "piso_usado": piso_dict(r.piso_usado),
        "achados": [achado_comparabilidade_dict(a) for a in r.achados],
    }


def _achado_lint_dict(a: AchadoLint) -> dict[str, object]:
    return {"tipo": a.tipo, "resumo": a.resumo, "evidencia": dict(a.evidencia)}


def achado_unificado_dict(a: AchadoUnificado) -> dict[str, object]:
    return {"tipo": a.origem, "resumo": a.resumo, "evidencia": dict(a.evidencia)}


def _segmento_risco_dict(s: SegmentoRisco) -> dict[str, object]:
    return {
        "nome": s.nome,
        "custo_total": str(s.custo_total),
        "unidades_ofertadas": s.unidades_ofertadas,
        "unidades_usadas": s.unidades_usadas,
        "taxa_aproveitamento": str(s.taxa_aproveitamento),
        "turnover_atribuido": (
            str(s.turnover_atribuido) if s.turnover_atribuido is not None else None
        ),
    }


def _risco_dict(r: ResultadoRisco) -> dict[str, object]:
    return {
        "fase": "risco",
        "casa": r.casa,
        "squad": r.squad,
        "acao": r.acao,
        "janela_inicio": r.janela_inicio,
        "janela_fim": r.janela_fim,
        "segmentos": [_segmento_risco_dict(s) for s in r.segmentos],
        "cobertura_pct": _numero_dict(r.cobertura_pct),
        "cobertura_piso": piso_dict(r.cobertura_piso),
        "cobertura_ok": r.cobertura_ok,
        "vies_selecao": (
            achado_unificado_dict(r.vies_selecao) if r.vies_selecao is not None else None
        ),
        "achados_governanca": [achado_unificado_dict(a) for a in r.achados_governanca],
    }


def _leitura_dict(leitura: ResultadoLeitura) -> dict[str, object]:
    return {
        "fase": "leitura",
        "casa": leitura.casa,
        "universo": leitura.universo,
        "campanha_id": leitura.campanha_id,
        "janela_inicio": leitura.janela_inicio,
        "janela_fim": leitura.janela_fim,
        "hipotese": leitura.hipotese,
        "contexto": leitura.contexto,
        "digest_hash": leitura.digest_hash,
        "bracos": [_braco_dict(b) for b in leitura.bracos],
        "c3": c3_dict(leitura.c3) if leitura.c3 is not None else None,
        "c2": c2_dict(leitura.c2) if leitura.c2 is not None else None,
        "achados": [_achado_lint_dict(a) for a in leitura.achados],
    }
