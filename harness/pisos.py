"""Pisos P3 com lineage (B1).

Os tres pisos sao decisao de negocio real; esperar a decisao congelaria o M3.
Com default versionado, decidir vira um diff de uma linha no CRM.md -- e
enquanto ninguem decide, todo LintResult que usar um piso carrega qual valor
e qual origem, honestamente rotulado "default_nao_validado".
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

# "cli": operador digitou o valor na linha de comando para esta execucao
# (ex.: piso_mde_ok, sem tabela de default nem linha em CRM.md). E a origem
# menos confiavel das tres -- nao foi decidida em reuniao nem versionada.
Origem = Literal["default_nao_validado", "crm_md", "cli"]


@dataclass(frozen=True)
class Piso:
    valor: Decimal
    origem: Origem


_DEFAULTS: dict[str, Decimal] = {
    "C3_ENTREGA_MINIMA": Decimal("0.85"),
    "C2_DESVIO_MAX_BRACOS": Decimal("0.05"),
    "C_AMOSTRA_MIN_CONTRASTE": Decimal("30"),
    # B3.1: default dado explicitamente pelo prompt ("piso (default 0.60)").
    "CTOR_MAX_ANOMALO": Decimal("0.60"),
    # E23: corte de cobertura de dado abaixo do qual um VeredictoRisco fica
    # suspenso (nao suprimido -- so marcado cobertura_ok=False, mesmo
    # espirito de C3). Valor observado na pratica pelo relatorio de
    # torneios da brand-a (abaixo de 90% -> resultado suspenso para o universo
    # total), nunca decidido em reuniao -- mesma origem de C3_ENTREGA_MINIMA.
    "COBERTURA_MIN_DADO": Decimal("0.90"),
}

_LINHA_TABELA = re.compile(r"^\|\s*([A-Z0-9_]+)\s*\|\s*([0-9.]+)\s*\|")


def _busca_em_crm_md(nome: str, caminho: Path) -> Decimal | None:
    """Le a secao '## 6' de CRM.md por uma linha de tabela '| NOME | valor |'."""
    if not caminho.exists():
        return None
    texto = caminho.read_text(encoding="utf-8")
    marcador = "## 6"
    if marcador not in texto:
        return None
    secao = texto.split(marcador, 1)[1]
    proxima = secao.find("\n## ")
    if proxima != -1:
        secao = secao[:proxima]
    for linha in secao.splitlines():
        m = _LINHA_TABELA.match(linha.strip())
        if m and m.group(1) == nome:
            return Decimal(m.group(2))
    return None


def carrega_piso(nome: str, *, caminho_crm_md: Path = Path("CRM.md")) -> Piso:
    if nome not in _DEFAULTS:
        raise ValueError(f"piso desconhecido: {nome!r}")
    valor_crm = _busca_em_crm_md(nome, caminho_crm_md)
    if valor_crm is not None:
        return Piso(valor_crm, "crm_md")
    return Piso(_DEFAULTS[nome], "default_nao_validado")
