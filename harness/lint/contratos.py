"""Contrato unificado do runner de lint (harness/lint/runner.py).

Vive em harness/lint/, nao em harness/contracts.py: LintResult/ResultadoLint
sao vocabulario do subsistema de lint (gates C + detectores B), nao um tipo
de dominio atravessado por ingest/preflight/publica como Digest ou
SpecCampanha. Colocar aqui evita que o contracts.py de raiz (importado por
quase tudo) passe a depender de harness.lint -- a dependencia vai na
direcao contraria (runner.py importa daqui), como o resto do pacote ja
faz (preflight.py e documento.py tambem guardam seus proprios tipos perto
de quem os usa).

Cada gate hoje devolve seu proprio tipo (ResultadoC3, ResultadoComparabilidade)
e nenhum ponto do codigo os reune com os detectores de achados.py -- LintResult
e o formato comum que o runner produz por gate; ResultadoLint e a agregacao
de todos os gates do ROSTER mais os achados de todos os detectores B, num
unico canal.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from harness.pisos import Piso

Veredito = Literal["verde", "vermelho", "indeterminado"]

# Fechado de proposito -- motivo e codigo estruturado (para o modelo/relatorio
# decidir o proximo passo), nao prosa livre (isso e o campo `resumo` de cada
# achado). Quatro causas cobrem tudo que os gates hoje produzem:
#   dado_valido              -- verde: gate rodou, decisao ficou de pe (achados,
#                               se houver, so anexam evidencia -- nao rebaixam).
#                               Nao chama "piso_ok" -- nem todo gate tem piso
#                               (C6-ordem nao tem nenhum) e o nome nao pode
#                               mentir sobre o que aconteceu.
#   dado_invalido            -- vermelho: dado estruturalmente impossivel
#                               (ex.: entregue > enviado em c3_entrega)
#   dado_insuficiente         -- indeterminado: braco(s) avaliavel(is) de menos
#                               para o gate decidir (c3 sem etapa medida, c2
#                               com menos de dois bracos avaliaveis)
#   gate_nao_implementado    -- vermelho: ROSTER declara o gate, REGISTRO nao
#                               tem implementacao (item 3 do runner)
Motivo = Literal["dado_valido", "dado_invalido", "dado_insuficiente", "gate_nao_implementado"]


@dataclass(frozen=True)
class AchadoUnificado:
    """Acaba com a divergencia de forma entre Achado de c3.py (evidencia em
    Decimal), AchadoComparabilidade (idem) e Achado de achados.py (evidencia
    em int). `origem` e o gate ("C3", "C2") ou o `tipo` do detector
    ("ctor_anomalo", "optout_alto"); evidencia vira str em todo mundo --
    achatar o canal exige um unico formato, nao tres.

    `bracos` carrega a atribuicao por braco que cada gate ja media (c3.py
    nunca soma entrega entre bracos -- ver docstring de c3_entrega): vazio
    para achado de detector (nao e por braco), um elemento para C3 (o
    braco avaliado), dois para C2 (os dois bracos contrastados, na ordem
    maior/menor de entrega). Perder isso na flattening seria reintroduzir
    o mesmo defeito que a avaliacao por braco corrigiu.
    """

    origem: str
    resumo: str
    evidencia: Mapping[str, str]
    bracos: tuple[str, ...] = ()


@dataclass(frozen=True)
class LintResult:
    """Resultado unificado de um gate do ROSTER (harness/lint/runner.py).

    piso_usado e None quando o gate nao tem implementacao (motivo
    "gate_nao_implementado" -- nenhum piso foi carregado porque nenhum
    gate rodou) OU quando o gate roda mas nao tem piso nenhum (ex.:
    C6-ordem -- ordem temporal impossivel nao e questao de piso).
    """

    gate: str
    veredito: Veredito
    motivo: Motivo
    achados: tuple[AchadoUnificado, ...]
    piso_usado: Piso | None


@dataclass(frozen=True)
class ResultadoLint:
    """Saida de roda_lint: veredito agregado (vermelho > indeterminado >
    verde, item 5), um LintResult por gate do ROSTER na ordem do ROSTER, e
    os achados de gates + detectores B achatados num canal so.
    """

    veredito: Veredito
    resultados: tuple[LintResult, ...]
    achados: tuple[AchadoUnificado, ...]
