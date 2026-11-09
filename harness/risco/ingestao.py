"""Ingestao do JSON que um risk squad entrega ao final de uma analise (E23).

Le, valida a forma EXATA (nunca um subconjunto de chaves, mesmo espirito de
ParametrosDivergentes/DigestComFormaInesperada) e devolve VeredictoRisco.
Nao chama MCP, nao roda SQL, nao toca rede -- so le o arquivo que o squad
ja produziu e decide se o formato bate com o contrato.
"""

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from harness.contracts import Numero
from harness.lint.contratos import AchadoUnificado
from harness.pisos import carrega_piso
from harness.risco.contratos import SegmentoRisco, VeredictoRisco, avalia_cobertura

_CHAVES_TOPO = frozenset({
    "casa", "squad", "acao", "janela_inicio", "janela_fim",
    "segmentos", "cobertura_pct", "vies_selecao", "achados_governanca",
})
_CHAVES_SEGMENTO = frozenset({
    "nome", "custo_total", "unidades_ofertadas", "unidades_usadas",
    "taxa_aproveitamento", "turnover_atribuido",
})
_CHAVES_ACHADO = frozenset({"tipo", "resumo", "evidencia"})
_CHAVES_COBERTURA = frozenset({"valor", "rotulo"})


class ChavesDivergentes(Exception):
    """Um dict (topo, segmento ou achado) nao tem exatamente as chaves
    esperadas -- nunca aceita subconjunto nem ignora chave extra."""

    def __init__(self, contexto: str, faltando: tuple[str, ...], sobrando: tuple[str, ...]) -> None:
        self.contexto = contexto
        self.faltando = faltando
        self.sobrando = sobrando
        super().__init__(
            f"{contexto}: chaves esperadas nao batem "
            f"(faltando={list(faltando)}, sobrando={list(sobrando)})"
        )


def _confere_chaves(dados: dict[str, Any], esperadas: frozenset[str], contexto: str) -> None:
    fornecidas = set(dados)
    if fornecidas != esperadas:
        raise ChavesDivergentes(
            contexto,
            tuple(sorted(esperadas - fornecidas)),
            tuple(sorted(fornecidas - esperadas)),
        )


def _le_segmento(dados: dict[str, Any], *, indice: int) -> SegmentoRisco:
    _confere_chaves(dados, _CHAVES_SEGMENTO, f"segmentos[{indice}]")
    turnover = dados["turnover_atribuido"]
    return SegmentoRisco(
        nome=dados["nome"],
        custo_total=Decimal(dados["custo_total"]),
        unidades_ofertadas=dados["unidades_ofertadas"],
        unidades_usadas=dados["unidades_usadas"],
        taxa_aproveitamento=Decimal(dados["taxa_aproveitamento"]),
        turnover_atribuido=Decimal(turnover) if turnover is not None else None,
    )


def _le_achado(dados: dict[str, Any], *, contexto: str) -> AchadoUnificado:
    _confere_chaves(dados, _CHAVES_ACHADO, contexto)
    return AchadoUnificado(
        origem=dados["tipo"], resumo=dados["resumo"], evidencia=dict(dados["evidencia"]),
    )


def _le_cobertura(dados: dict[str, Any]) -> Numero:
    """{"valor": "0.795", "rotulo": "medido"} ou {"valor": null, "rotulo":
    "ausente"} -- mesma forma de EtapaFunil.volume (harness/contracts.py).
    Numero.__post_init__ ja recusa valor+rotulo inconsistentes (E24)."""
    _confere_chaves(dados, _CHAVES_COBERTURA, "cobertura_pct")
    valor = dados["valor"]
    return Numero(Decimal(valor) if valor is not None else None, dados["rotulo"])


def ingere(caminho: Path) -> VeredictoRisco:
    bruto = caminho.read_text(encoding="utf-8")
    dados = json.loads(bruto)
    _confere_chaves(dados, _CHAVES_TOPO, str(caminho))

    segmentos = tuple(
        _le_segmento(s, indice=i) for i, s in enumerate(dados["segmentos"])
    )
    vies = dados["vies_selecao"]
    vies_selecao = _le_achado(vies, contexto="vies_selecao") if vies is not None else None
    achados_governanca = tuple(
        _le_achado(a, contexto=f"achados_governanca[{i}]")
        for i, a in enumerate(dados["achados_governanca"])
    )

    cobertura_pct = _le_cobertura(dados["cobertura_pct"])
    piso = carrega_piso("COBERTURA_MIN_DADO")

    return VeredictoRisco(
        fase="risco",
        casa=dados["casa"],
        squad=dados["squad"],
        acao=dados["acao"],
        janela_inicio=dados["janela_inicio"],
        janela_fim=dados["janela_fim"],
        segmentos=segmentos,
        cobertura_pct=cobertura_pct,
        cobertura_piso=piso,
        cobertura_ok=avalia_cobertura(cobertura_pct, piso),
        vies_selecao=vies_selecao,
        achados_governanca=achados_governanca,
        proveniencia={
            "fonte": "squad",
            "squad": dados["squad"],
            "caminho": str(caminho),
            "sha256": hashlib.sha256(bruto.encode("utf-8")).hexdigest(),
        },
    )
