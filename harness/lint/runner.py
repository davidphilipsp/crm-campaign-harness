"""Runner de lint: reune gates C e detectores B num ResultadoLint so.

Funcao pura -- sem I/O, sem relogio, sem leitura de disco. O runner nunca
chama harness.pisos.carrega_piso (isso seria I/O: carrega_piso le CRM.md do
disco) -- todos os pisos, de gate e de detector, entram resolvidos via o
parametro `pisos` de roda_lint. Quem le CRM.md/disco e o caller (cli.py,
fiacao do commit seguinte), o mesmo padrao que ja rege c3.py e preflight.py:
gate/runner nunca carrega piso por dentro.

Por que este modulo existe: cada gate hoje devolve seu proprio tipo
(ResultadoC3, ResultadoComparabilidade) e nenhum ponto do codigo reune gates
C com os detectores de achados.py -- por isso detecta_ctor_anomalo e
detecta_optout_alto nunca sao chamados por ninguem em producao. Este runner
e o unico lugar que conhece os dois mundos; harness/cli.py, persist/ e
publica/ continuam sem mudar nesta etapa (a fiacao entra depois).
"""

from collections.abc import Callable, Mapping, Sequence

from harness.contracts import Braco, Digest
from harness.lint.achados import Achado as AchadoDetector
from harness.lint.achados import detecta_ctor_anomalo, detecta_optout_alto
from harness.lint.c3 import Achado as AchadoC3
from harness.lint.c3 import (
    AchadoComparabilidade,
    ResultadoC3,
    ResultadoComparabilidade,
    c3_entrega,
    entrega_comparavel,
)
from harness.lint.contratos import AchadoUnificado, LintResult, Motivo, ResultadoLint, Veredito
from harness.lint.ordem_temporal import Achado as AchadoOrdemTemporal
from harness.lint.ordem_temporal import Resultado as ResultadoOrdemTemporal
from harness.lint.ordem_temporal import avalia_ordem_temporal
from harness.pisos import Piso

# Identificadores declarados (CRM.md §4 P1/P2, Modulo 2). O runner itera
# ROSTER, nao REGISTRO -- um gate sem implementacao ainda aparece no
# resultado, vermelho por ausencia (item 3), em vez de simplesmente sumir.
# "C6-ordem" e sub-cheque de C6 (filiacao so pelo nome -- ROSTER e uma
# tupla achatada, sem campo de parentesco, mesma situacao de "C1-b" com
# "C1"): NAO substitui "C6" nem reduz gates_ausentes -- C6 propriamente
# dito (CRM.md P7) continua sem implementacao.
ROSTER: tuple[str, ...] = (
    "C1", "C1-b", "C2", "C3", "C4", "C5", "C6", "C6-ordem", "C7",
)

_PISO_C3 = "C3_ENTREGA_MINIMA"
_PISO_C2 = "C2_DESVIO_MAX_BRACOS"
_PISO_CTOR = "CTOR_MAX_ANOMALO"
# achados.py documenta piso_optout como parametro obrigatorio SEM default em
# harness.pisos (nenhuma linha em _DEFAULTS) -- nao inventamos um nome de
# constante de negocio para ele; a chave usada aqui e o proprio nome do
# parametro de detecta_optout_alto, so para o runner saber qual entrada de
# `pisos` procurar. Ausente => detector pendente (ver _roda_detectores).
_PISO_OPTOUT = "piso_optout"


class PisoAusente(Exception):
    """Gate implementado, mas o caller nao injetou o piso que ele exige.

    Diferente do detector B (que so fica pendente sem levantar -- ver
    _roda_detectores): um gate do REGISTRO tem contrato firme com seu piso;
    rodar sem ele e erro de wiring do caller, nao ausencia de decisao de
    negocio.
    """

    def __init__(self, gate: str, chave: str) -> None:
        self.gate = gate
        self.chave = chave
        super().__init__(f"gate {gate} exige piso {chave!r}, ausente em `pisos`")


def _piso_obrigatorio(pisos: Mapping[str, Piso], chave: str, *, gate: str) -> Piso:
    piso = pisos.get(chave)
    if piso is None:
        raise PisoAusente(gate, chave)
    return piso


def _evidencia_str(evidencia: Mapping[str, object]) -> dict[str, str]:
    return {chave: str(valor) for chave, valor in evidencia.items()}


def _achado_de_c3(a: AchadoC3) -> AchadoUnificado:
    return AchadoUnificado(
        origem="C3", resumo=a.resumo, evidencia=_evidencia_str(a.evidencia), bracos=(a.braco,)
    )


def _achado_de_c2(a: AchadoComparabilidade) -> AchadoUnificado:
    return AchadoUnificado(
        origem="C2", resumo=a.resumo, evidencia=_evidencia_str(a.evidencia), bracos=a.bracos
    )


def _achado_de_detector(nome: str, braco_nome: str, a: AchadoDetector) -> AchadoUnificado:
    return AchadoUnificado(
        origem=nome, resumo=a.resumo, evidencia=_evidencia_str(a.evidencia), bracos=(braco_nome,)
    )


def _motivo_por_veredito_de_dado(veredito: Veredito) -> Motivo:
    """C3, C2 e C6-ordem so decidem por qualidade/suficiencia do dado --
    nunca ha uma terceira razao para vermelho/indeterminado nesses tres
    gates hoje. "dado_valido" (LintResult.motivo, harness/lint/contratos.py)
    cobre o verde dos tres, com ou sem piso -- C6-ordem nao tem piso
    nenhum, entao o motivo nao pode se chamar "piso_ok"."""
    if veredito == "vermelho":
        return "dado_invalido"
    if veredito == "indeterminado":
        return "dado_insuficiente"
    return "dado_valido"


def _resultado_c3_em_lint(r: ResultadoC3) -> LintResult:
    return LintResult(
        gate="C3",
        veredito=r.veredito,
        motivo=_motivo_por_veredito_de_dado(r.veredito),
        achados=tuple(_achado_de_c3(a) for a in r.achados),
        piso_usado=r.piso_usado,
    )


def _resultado_c2_em_lint(r: ResultadoComparabilidade) -> LintResult:
    return LintResult(
        gate="C2",
        veredito=r.veredito,
        motivo=_motivo_por_veredito_de_dado(r.veredito),
        achados=tuple(_achado_de_c2(a) for a in r.achados),
        piso_usado=r.piso_usado,
    )


def _executa_c3(digest: Digest, pisos: Mapping[str, Piso]) -> LintResult:
    piso = _piso_obrigatorio(pisos, _PISO_C3, gate="C3")
    return _resultado_c3_em_lint(c3_entrega(digest, piso=piso))


def _executa_c2(digest: Digest, pisos: Mapping[str, Piso]) -> LintResult:
    piso = _piso_obrigatorio(pisos, _PISO_C2, gate="C2")
    return _resultado_c2_em_lint(entrega_comparavel(digest, piso=piso))


def _achado_de_ordem_temporal(a: AchadoOrdemTemporal) -> AchadoUnificado:
    return AchadoUnificado(
        origem="C6-ordem", resumo=a.resumo, evidencia=_evidencia_str(a.evidencia), bracos=(a.braco,)
    )


def _resultado_ordem_temporal_em_lint(r: ResultadoOrdemTemporal) -> LintResult:
    return LintResult(
        gate="C6-ordem",
        veredito=r.veredito,
        motivo=_motivo_por_veredito_de_dado(r.veredito),
        achados=tuple(_achado_de_ordem_temporal(a) for a in r.achados),
        piso_usado=None,
    )


def _executa_c6_ordem(digest: Digest, pisos: Mapping[str, Piso]) -> LintResult:
    """Assinatura igual aos outros executores de REGISTRO (Callable[[Digest,
    Mapping[str, Piso]], LintResult]) pra caber no mesmo dict -- `pisos`
    nunca e tocado: C6-ordem nao tem piso (dado impossivel nao e questao
    de piso de negocio)."""
    return _resultado_ordem_temporal_em_lint(avalia_ordem_temporal(digest))


# So os gates com implementacao real entram aqui -- o runner itera ROSTER,
# nunca REGISTRO (item 2): um gate do roster que nao esta neste dict vira
# vermelho por ausencia em _roda_gate, nunca some do resultado.
REGISTRO: dict[str, Callable[[Digest, Mapping[str, Piso]], LintResult]] = {
    "C3": _executa_c3,
    "C2": _executa_c2,
    "C6-ordem": _executa_c6_ordem,
}


def _roda_gate(gate: str, digest: Digest, pisos: Mapping[str, Piso]) -> LintResult:
    executor = REGISTRO.get(gate)
    if executor is None:
        return LintResult(
            gate=gate,
            veredito="vermelho",
            motivo="gate_nao_implementado",
            achados=(),
            piso_usado=None,
        )
    return executor(digest, pisos)


_PRECEDENCIA: dict[Veredito, int] = {"verde": 0, "indeterminado": 1, "vermelho": 2}


def _agrega(veredictos: Sequence[Veredito]) -> Veredito:
    pior: Veredito = "verde"
    for v in veredictos:
        if _PRECEDENCIA[v] > _PRECEDENCIA[pior]:
            pior = v
    return pior


def _executa_ctor(braco: Braco, piso: Piso) -> AchadoDetector | None:
    return detecta_ctor_anomalo(braco, piso_ctor=piso)


def _executa_optout(braco: Braco, piso: Piso) -> AchadoDetector | None:
    return detecta_optout_alto(braco, piso_optout=piso)


def _ctor_dado_ausente(digest: Digest) -> bool:
    return any(
        numero.rotulo == "ausente"
        for braco in digest.bracos
        for _, numero in braco.latencia_entrega_clique
    )


def _optout_dado_ausente(digest: Digest) -> bool:
    return any(braco.optout.rotulo == "ausente" for braco in digest.bracos)


class _DetectorSpec:
    """So produzem achados, nunca veredito (item 4) -- por isso nao ha
    LintResult para detector, so entradas no canal de achados.

    dado_ausente e so para o relatorio (cli.py): distingue "rodou, nao
    achou nada" (achado None comum) de "nao rodou porque o digest
    arquivado nao tem esse campo" -- a funcao detectora tambem devolve
    None nos dois casos, entao o report generico via DETECTORES precisa
    de outro jeito de saber qual dos dois aconteceu.
    """

    __slots__ = ("nome", "piso_chave", "funcao", "dado_ausente")

    def __init__(
        self,
        nome: str,
        piso_chave: str,
        funcao: Callable[[Braco, Piso], AchadoDetector | None],
        dado_ausente: Callable[[Digest], bool],
    ) -> None:
        self.nome = nome
        self.piso_chave = piso_chave
        self.funcao = funcao
        self.dado_ausente = dado_ausente


# detecta_optout_alto entra pendente: sem default em harness.pisos e sem o
# runner inventar um ou chamar carrega_piso -- se `pisos` nao tiver a chave,
# o detector so nao roda (ver _roda_detectores), nunca levanta.
DETECTORES: tuple[_DetectorSpec, ...] = (
    _DetectorSpec("ctor_anomalo", _PISO_CTOR, _executa_ctor, _ctor_dado_ausente),
    _DetectorSpec("optout_alto", _PISO_OPTOUT, _executa_optout, _optout_dado_ausente),
)


def _roda_detectores(digest: Digest, pisos: Mapping[str, Piso]) -> tuple[AchadoUnificado, ...]:
    """Um detector por braco -- os dois agora leem so do Digest (histograma
    de latencia, contador de optout, etapas), a mesma fonte que os gates C
    usam. Nao ha mais `linhas`: Digest relido do disco carrega exatamente o
    que a ingestao fresca carregava, entao roda_ingest e a leitura de um
    digest ja gravado (harness.cli.roda_lint_cli) deixam de divergir."""
    achados: list[AchadoUnificado] = []
    for spec in DETECTORES:
        piso = pisos.get(spec.piso_chave)
        if piso is None:
            continue
        for braco in digest.bracos:
            achado = spec.funcao(braco, piso)
            if achado is not None:
                achados.append(_achado_de_detector(spec.nome, braco.nome, achado))
    return tuple(achados)


def roda_lint(digest: Digest, *, pisos: Mapping[str, Piso]) -> ResultadoLint:
    """Roda o ROSTER de gates e os DETECTORES sobre `digest` -- os dois
    mundos leem exclusivamente do Digest agora, sem parametro `linhas`.
    Isso e o que faz roda_ingest (digest fresco) e a releitura de um
    resultado persistido (harness.cli.roda_lint_cli) produzirem a mesma
    lista de achados: nao ha mais uma fonte de dado que soma existe num
    dos dois caminhos.

    Agregacao (item 5): veredito vermelho vence indeterminado, que vence
    verde; achados de gates e de detectores B saem no mesmo campo `achados`,
    achatados, sem tag de "gate" vs "detector" alem do proprio `origem`.
    """
    resultados = tuple(_roda_gate(gate, digest, pisos) for gate in ROSTER)
    achados_gates = tuple(a for r in resultados for a in r.achados)
    achados_detectores = _roda_detectores(digest, pisos)
    veredito = _agrega(tuple(r.veredito for r in resultados))
    return ResultadoLint(
        veredito=veredito,
        resultados=resultados,
        achados=achados_gates + achados_detectores,
    )
