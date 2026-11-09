"""Persistencia de resultados de leitura (P0).

Embriao do ledger de Z2 (M4): JSON por execucao, nome ordenavel por tempo,
nunca sobrescrito -- mas sem hash encadeado nem append-only ainda. Isso vem
depois, sem mudar este formato (campos so se acrescentam).
"""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from harness.contracts import (
    ORDEM_BUCKETS_LATENCIA,
    Braco,
    BucketLatencia,
    Digest,
    EtapaFunil,
    Numero,
)
from harness.digest import _serializa, digest_hash
from harness.lint.c3 import Achado as AchadoC3
from harness.lint.c3 import AchadoComparabilidade, ResultadoC3, ResultadoComparabilidade
from harness.lint.contratos import AchadoUnificado, LintResult, Motivo, ResultadoLint, Veredito
from harness.pisos import Piso
from harness.preflight import ResultadoMDE, SpecCampanha, VeredictoPreflight
from harness.publica.documento import c8_dict, veredicto_preflight_dict
from harness.risco.contratos import SegmentoRisco, VeredictoRisco

SAIDA_PADRAO = Path("resultados")


def _achado_unificado_dict(a: AchadoUnificado) -> dict[str, Any]:
    """Mesma chave "tipo" do contrato do consumidor downstream (references/consumer-
    interface.md) para o campo homonimo -- AchadoUnificado
    chama esse campo `origem` (harness/lint/contratos.py, congelado), mas o
    JSON gravado usa "tipo" para que o mesmo dict sirva sem tradução quando
    vira achado de detector no documento publicado. `bracos` e canal interno
    (ledger, RF-05) -- o contrato do consumidor downstream nao tem esse campo no topo,
    so dentro de lints.c3/lints.c2 (ver _projeta_c3/_projeta_c2)."""
    return {
        "tipo": a.origem,
        "resumo": a.resumo,
        "evidencia": dict(a.evidencia),
        "bracos": list(a.bracos),
    }


def _projeta_c3(lr: LintResult) -> dict[str, Any]:
    """Projeta lints.c3 do LintResult de C3 -- mesmo formato byte a byte
    que documento.c3_dict produzia a partir de ResultadoC3 (achado carrega
    `braco` desde que AchadoUnificado ganhou o campo `bracos`)."""
    piso = lr.piso_usado
    if piso is None:
        raise ValueError(f"LintResult({lr.gate!r}) sem piso_usado -- gate nao rodou")
    return {
        "veredito": lr.veredito,
        "piso_usado": {"valor": str(piso.valor), "origem": piso.origem},
        "achados": [
            {
                "gate": lr.gate, "braco": a.bracos[0],
                "resumo": a.resumo, "evidencia": dict(a.evidencia),
            }
            for a in lr.achados
        ],
    }


def _projeta_c2(lr: LintResult) -> dict[str, Any]:
    """Projeta lints.c2 do LintResult de C2 -- mesmo formato byte a byte
    que documento.c2_dict produzia a partir de ResultadoComparabilidade."""
    piso = lr.piso_usado
    if piso is None:
        raise ValueError(f"LintResult({lr.gate!r}) sem piso_usado -- gate nao rodou")
    return {
        "veredito": lr.veredito,
        "piso_usado": {"valor": str(piso.valor), "origem": piso.origem},
        "achados": [
            {"gate": lr.gate, "bracos": list(a.bracos), "resumo": a.resumo,
             "evidencia": dict(a.evidencia)}
            for a in lr.achados
        ],
    }


def _lints_de_resultado_lint(resultado_lint: ResultadoLint | None) -> dict[str, Any]:
    """C3/C2 nao carregam piso proprio nesta fronteira: sao projetados do
    LintResult que harness.lint.runner.roda_lint ja calculou -- unica vez,
    nao de novo aqui. Pula gate que nao rodou de verdade (motivo ==
    "gate_nao_implementado") -- a condicao que "piso_usado is None" so
    testava por coincidencia: C3/C2 sempre tem piso quando implementados,
    mas C6-ordem tem piso_usado None por natureza (nao por ausencia) e
    nao pode ser confundido com "nao implementado" aqui."""
    if resultado_lint is None:
        return {}
    lints: dict[str, Any] = {}
    for lr in resultado_lint.resultados:
        if lr.motivo == "gate_nao_implementado":
            continue
        if lr.gate == "C3":
            lints["c3"] = _projeta_c3(lr)
        elif lr.gate == "C2":
            lints["c2"] = _projeta_c2(lr)
    return lints


def _piso_dict_ou_none(piso: Piso | None) -> dict[str, Any] | None:
    return None if piso is None else {"valor": str(piso.valor), "origem": piso.origem}


def _piso_ou_none(dados: dict[str, Any] | None) -> Piso | None:
    return None if dados is None else _piso(dados)


def _lint_result_dict(lr: LintResult) -> dict[str, Any]:
    """Canal generico (chave "gates"): projeta QUALQUER LintResult -- gate,
    veredito, motivo, achados, piso_usado, os cinco campos que o tipo tem
    -- sem ramificar por nome. Aditivo a lints.c3/lints.c2 (_projeta_c3/
    _projeta_c2, acima), que continuam byte a byte identicos: aquele
    canal alimenta o contrato congelado do consumidor downstream, este e o unico
    lugar onde um veredito de QUALQUER gate (C6-ordem incluso) fica
    registrado com causa, nao so em print()."""
    return {
        "gate": lr.gate,
        "veredito": lr.veredito,
        "motivo": lr.motivo,
        "achados": [_achado_unificado_dict(a) for a in lr.achados],
        "piso_usado": _piso_dict_ou_none(lr.piso_usado),
    }


def _gates_de_resultado_lint(resultado_lint: ResultadoLint | None) -> list[dict[str, Any]]:
    if resultado_lint is None:
        return []
    return [_lint_result_dict(lr) for lr in resultado_lint.resultados]


def grava_resultado(
    digest: Digest,
    *,
    saida: Path = SAIDA_PADRAO,
    agora: datetime | None = None,
    resultado_lint: ResultadoLint | None = None,
) -> Path:
    """Grava resultados/<casa>/<campanha_id>/<timestamp>.json.

    Nunca sobrescreve -- colisao de nome estoura em vez de apagar um
    resultado existente (ledger embriao: cada execucao e um registro novo).

    resultado_lint e a saida de harness.lint.runner.roda_lint -- unica
    fonte de lints.c3/lints.c2 (projetados aqui, na fronteira de
    persistencia, do LintResult de cada gate; C3/C2 sao calculados uma vez
    so, dentro de roda_lint -- roda_ingest nao chama c3_entrega/
    entrega_comparavel diretamente mais), do canal achatado `achados`
    (gates + detectores B), do veredito agregado + gates ausentes em
    "lint", e de "gates" -- todo LintResult de resultado_lint.resultados,
    sem ramificar por nome de gate: nenhum gate nasce invisivel aqui,
    nem os que nao tem piso (C6-ordem) nem os ainda nao implementados.
    None (nenhum lint rodou) grava lints={}, achados=[], lint=None,
    gates=[] -- mesmo formato de antes de qualquer lint existir.
    """
    momento = agora if agora is not None else datetime.now(UTC)
    destino = saida / digest.casa / digest.campanha_id
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / f"{momento.strftime('%Y%m%dT%H%M%S.%f')}Z.json"

    if caminho.exists():
        raise FileExistsError(f"resultado ja existe, nunca sobrescreve: {caminho}")

    achados = resultado_lint.achados if resultado_lint is not None else ()
    lint_resumo = (
        {
            "veredito": resultado_lint.veredito,
            "gates_ausentes": [
                lr.gate for lr in resultado_lint.resultados if lr.motivo == "gate_nao_implementado"
            ],
        }
        if resultado_lint is not None
        else None
    )

    dados: dict[str, Any] = {
        "gravado_em": momento.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
        "digest": digest.como_dict(),
        "digest_hash": digest_hash(digest.como_dict()),
        "lints": _lints_de_resultado_lint(resultado_lint),
        "achados": [_achado_unificado_dict(a) for a in achados],
        "lint": lint_resumo,
        "gates": _gates_de_resultado_lint(resultado_lint),
    }
    caminho.write_text(
        json.dumps(dados, sort_keys=True, ensure_ascii=False, default=_serializa),
        encoding="utf-8",
    )
    return caminho


def grava_preflight(
    spec: SpecCampanha,
    *,
    saida: Path = SAIDA_PADRAO,
    agora: datetime | None = None,
    c8: ResultadoMDE | None = None,
    c9: VeredictoPreflight | None = None,
    c11: VeredictoPreflight | None = None,
) -> Path:
    """Grava resultados/<casa>/<regua>/<timestamp>.json, fase 'preflight'.

    Mesmo esquema de grava_resultado (nunca sobrescreve, nome ordenavel por
    tempo). Envelope usa a chave "spec" em vez de "digest" -- e o que
    roda_publica usa para separar preflight de leitura em resultados/.
    """
    momento = agora if agora is not None else datetime.now(UTC)
    destino = saida / spec.casa / spec.regua
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / f"{momento.strftime('%Y%m%dT%H%M%S.%f')}Z.json"

    if caminho.exists():
        raise FileExistsError(f"resultado ja existe, nunca sobrescreve: {caminho}")

    dados: dict[str, Any] = {
        "gravado_em": momento.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
        "spec": asdict(spec),
        "c8": c8_dict(c8) if c8 is not None else None,
        "c9": veredicto_preflight_dict(c9) if c9 is not None else None,
        "c11": veredicto_preflight_dict(c11) if c11 is not None else None,
    }
    caminho.write_text(
        json.dumps(dados, sort_keys=True, ensure_ascii=False, default=_serializa),
        encoding="utf-8",
    )
    return caminho


class DigestComFormaInesperada(Exception):
    """Uma chave existe no dict persistido, mas o valor dela nao tem a
    forma que le_digest espera (Numero: {'valor':..., 'rotulo':...}; ou o
    conjunto de baldes de latencia diferente do declarado em
    ORDEM_BUCKETS_LATENCIA). Nunca tenta adivinhar ou coagir -- levanta,
    porque um numero errado aqui vira decisao silenciosa mais adiante."""


def _numero_de_dict(dados: object, *, contexto: str) -> Numero:
    if not isinstance(dados, dict) or set(dados) != {"valor", "rotulo"}:
        raise DigestComFormaInesperada(
            f"{contexto}: esperava Numero (chaves 'valor'+'rotulo'), achei {dados!r}"
        )
    valor = dados["valor"]
    return Numero(Decimal(valor) if valor is not None else None, dados["rotulo"])


def _optout_de_braco(b: dict[str, Any]) -> Numero:
    """Chave ausente => [ausente]: digest arquivado antes deste campo
    existir. NAO e dict.get com zero -- zero medido e zero ausente sao
    rotulos diferentes (ver harness/lint/achados.py)."""
    if "optout" not in b:
        return Numero(None, "ausente")
    return _numero_de_dict(b["optout"], contexto="optout")


def _latencia_de_braco(b: dict[str, Any]) -> tuple[tuple[BucketLatencia, Numero], ...]:
    """Chave ausente => todos os baldes [ausente] (mesmo raciocinio de
    _optout_de_braco). Chave presente com baldes errados ou incompletos
    => DigestComFormaInesperada, nunca um subconjunto silencioso."""
    if "latencia_entrega_clique" not in b:
        return tuple((nome, Numero(None, "ausente")) for nome in ORDEM_BUCKETS_LATENCIA)

    bruto = b["latencia_entrega_clique"]
    if not isinstance(bruto, list):
        raise DigestComFormaInesperada(
            f"latencia_entrega_clique: esperava lista de pares [nome, Numero], achei {bruto!r}"
        )
    try:
        mapa = dict(bruto)
    except (TypeError, ValueError) as exc:
        raise DigestComFormaInesperada(
            f"latencia_entrega_clique: forma invalida: {bruto!r}"
        ) from exc
    if set(mapa) != set(ORDEM_BUCKETS_LATENCIA):
        raise DigestComFormaInesperada(
            f"latencia_entrega_clique: esperava exatamente os baldes "
            f"{ORDEM_BUCKETS_LATENCIA}, achei {sorted(mapa)}"
        )
    return tuple(
        (nome, _numero_de_dict(mapa[nome], contexto=f"latencia_entrega_clique[{nome!r}]"))
        for nome in ORDEM_BUCKETS_LATENCIA
    )


def le_digest(dados: dict[str, Any]) -> Digest:
    """Contra-parte de grava_resultado: reconstroi o Digest do dict lido de
    volta do disco (Decimal volta de str; list volta a tuple).

    Digest nao carrega marcador de versao de esquema (ver relatorio):
    latencia_entrega_clique/optout ausentes no dict persistido viram
    [ausente] (_optout_de_braco/_latencia_de_braco), nao KeyError e nao
    zero silencioso -- so uma chave presente com forma errada estoura
    DigestComFormaInesperada.
    """
    bracos = tuple(
        Braco(
            nome=b["nome"],
            etapas=tuple(
                EtapaFunil(
                    nome=e["nome"],
                    volume=Numero(
                        valor=(
                            Decimal(e["volume"]["valor"])
                            if e["volume"]["valor"] is not None
                            else None
                        ),
                        rotulo=e["volume"]["rotulo"],
                    ),
                )
                for e in b["etapas"]
            ),
            latencia_entrega_clique=_latencia_de_braco(b),
            optout=_optout_de_braco(b),
        )
        for b in dados["bracos"]
    )
    return Digest(
        casa=dados["casa"],
        fase=dados["fase"],
        universo=dados["universo"],
        campanha_id=dados["campanha_id"],
        janela_inicio=dados["janela_inicio"],
        janela_fim=dados["janela_fim"],
        hipotese=dados["hipotese"],
        contexto=dados["contexto"],
        bracos=bracos,
        proveniencia=dados["proveniencia"],
    )


def _piso(dados: dict[str, Any]) -> Piso:
    return Piso(Decimal(dados["valor"]), dados["origem"])


def le_c3(dados: dict[str, Any]) -> ResultadoC3:
    """Contra-parte de c3_dict (documento.py): reconstroi ResultadoC3."""
    return ResultadoC3(
        veredito=dados["veredito"],
        piso_usado=_piso(dados["piso_usado"]),
        achados=tuple(
            AchadoC3(
                gate=a["gate"],
                braco=a["braco"],
                resumo=a["resumo"],
                evidencia={k: Decimal(v) for k, v in a["evidencia"].items()},
            )
            for a in dados["achados"]
        ),
    )


def le_c2(dados: dict[str, Any]) -> ResultadoComparabilidade:
    """Contra-parte de c2_dict (documento.py): reconstroi ResultadoComparabilidade."""
    return ResultadoComparabilidade(
        veredito=dados["veredito"],
        piso_usado=_piso(dados["piso_usado"]),
        achados=tuple(
            AchadoComparabilidade(
                gate=a["gate"],
                bracos=tuple(a["bracos"]),
                resumo=a["resumo"],
                evidencia={k: Decimal(v) for k, v in a["evidencia"].items()},
            )
            for a in dados["achados"]
        ),
    )


def le_spec(dados: dict[str, Any]) -> SpecCampanha:
    """Contra-parte de grava_preflight: reconstroi SpecCampanha do dict lido."""
    return SpecCampanha(
        fase=dados["fase"],
        casa=dados["casa"],
        universo=dados["universo"],
        regua=dados["regua"],
        base_estimada=dados["base_estimada"],
        pct_holdout=Decimal(dados["pct_holdout"]),
        conversao_esperada=Decimal(dados["conversao_esperada"]),
        fonte_conversao_controle=dados["fonte_conversao_controle"],
        max_duration_s=dados["max_duration_s"],
        delays_s=tuple(dados["delays_s"]),
    )


def le_c8(dados: dict[str, Any]) -> ResultadoMDE:
    """Contra-parte de c8_dict (documento.py): reconstroi ResultadoMDE."""
    return ResultadoMDE(
        n_holdout=dados["n_holdout"],
        n_tratamento=dados["n_tratamento"],
        mde_absoluto=Decimal(dados["mde_absoluto"]),
        mde_relativo=Decimal(dados["mde_relativo"]),
        veredito=dados["veredito"],
        piso_amostra=_piso(dados["piso_amostra"]),
        piso_mde_ok=_piso(dados["piso_mde_ok"]),
        alternativas=tuple(dados["alternativas"]),
    )


def le_veredicto_preflight(dados: dict[str, Any]) -> VeredictoPreflight:
    """Contra-parte de veredicto_preflight_dict (documento.py): C9/C11."""
    return VeredictoPreflight(check=dados["check"], aprova=dados["aprova"], motivo=dados["motivo"])


def _achado_unificado_de_dict(a: dict[str, Any]) -> AchadoUnificado:
    return AchadoUnificado(
        origem=a["tipo"], resumo=a["resumo"], evidencia=dict(a["evidencia"]),
        bracos=tuple(a["bracos"]),
    )


def le_achados(dados: list[dict[str, Any]]) -> tuple[AchadoUnificado, ...]:
    """Contra-parte de _achado_unificado_dict: reconstroi os AchadoUnificado
    gravados na chave 'achados' -- lista vazia (chave sempre presente desde
    que este campo existe) reconstroi tupla vazia."""
    return tuple(_achado_unificado_de_dict(a) for a in dados)


def le_lint_resumo(dados: dict[str, Any] | None) -> tuple[Veredito, tuple[str, ...]] | None:
    """Contra-parte da chave 'lint' de grava_resultado: reconstroi
    (veredito agregado, gates ausentes). None quando nada foi gravado
    (caller nao rodou roda_lint)."""
    if dados is None:
        return None
    return dados["veredito"], tuple(dados["gates_ausentes"])


def le_lint_result(dados: dict[str, Any]) -> LintResult:
    """Contra-parte de _lint_result_dict: reconstroi UM LintResult da
    chave 'gates' -- os cinco campos do tipo, motivo incluido."""
    motivo: Motivo = dados["motivo"]
    return LintResult(
        gate=dados["gate"],
        veredito=dados["veredito"],
        motivo=motivo,
        achados=le_achados(dados["achados"]),
        piso_usado=_piso_ou_none(dados["piso_usado"]),
    )


def le_gates(dados: list[dict[str, Any]]) -> tuple[LintResult, ...]:
    """Contra-parte da chave 'gates' de grava_resultado: reconstroi todos
    os LintResult gravados, na mesma ordem -- lista vazia (chave sempre
    presente desde que este campo existe) reconstroi tupla vazia."""
    return tuple(le_lint_result(g) for g in dados)


def _segmento_risco_dict(s: SegmentoRisco) -> dict[str, Any]:
    return {
        "nome": s.nome,
        "custo_total": s.custo_total,
        "unidades_ofertadas": s.unidades_ofertadas,
        "unidades_usadas": s.unidades_usadas,
        "taxa_aproveitamento": s.taxa_aproveitamento,
        "turnover_atribuido": s.turnover_atribuido,
    }


def _le_segmento_risco(dados: dict[str, Any]) -> SegmentoRisco:
    turnover = dados["turnover_atribuido"]
    return SegmentoRisco(
        nome=dados["nome"],
        custo_total=Decimal(dados["custo_total"]),
        unidades_ofertadas=dados["unidades_ofertadas"],
        unidades_usadas=dados["unidades_usadas"],
        taxa_aproveitamento=Decimal(dados["taxa_aproveitamento"]),
        turnover_atribuido=Decimal(turnover) if turnover is not None else None,
    )


def grava_risco(
    veredicto: VeredictoRisco,
    *,
    saida: Path = SAIDA_PADRAO,
    agora: datetime | None = None,
) -> Path:
    """Grava resultados/<casa>/<acao>/<timestamp>.json, fase 'risco' (E23).

    Mesmo esquema de grava_resultado/grava_preflight -- nunca sobrescreve,
    nome ordenavel por tempo. Envelope usa a chave "risco"; roda_publica usa
    isso para distinguir dos outros dois tipos de envelope (eh_risco).
    """
    momento = agora if agora is not None else datetime.now(UTC)
    destino = saida / veredicto.casa / veredicto.acao
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / f"{momento.strftime('%Y%m%dT%H%M%S.%f')}Z.json"

    if caminho.exists():
        raise FileExistsError(f"resultado ja existe, nunca sobrescreve: {caminho}")

    dados: dict[str, Any] = {
        "gravado_em": momento.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
        "risco": {
            "fase": veredicto.fase,
            "casa": veredicto.casa,
            "squad": veredicto.squad,
            "acao": veredicto.acao,
            "janela_inicio": veredicto.janela_inicio,
            "janela_fim": veredicto.janela_fim,
            "segmentos": [_segmento_risco_dict(s) for s in veredicto.segmentos],
            "cobertura_pct": {
                "valor": veredicto.cobertura_pct.valor, "rotulo": veredicto.cobertura_pct.rotulo,
            },
            "cobertura_piso": _piso_dict_ou_none(veredicto.cobertura_piso),
            "cobertura_ok": veredicto.cobertura_ok,
            "vies_selecao": (
                _achado_unificado_dict(veredicto.vies_selecao)
                if veredicto.vies_selecao is not None
                else None
            ),
            "achados_governanca": [
                _achado_unificado_dict(a) for a in veredicto.achados_governanca
            ],
            "proveniencia": veredicto.proveniencia,
        },
    }
    caminho.write_text(
        json.dumps(dados, sort_keys=True, ensure_ascii=False, default=_serializa),
        encoding="utf-8",
    )
    return caminho


def le_risco(dados: dict[str, Any]) -> VeredictoRisco:
    """Contra-parte de grava_risco: reconstroi VeredictoRisco do dict lido."""
    vies = dados["vies_selecao"]
    return VeredictoRisco(
        fase=dados["fase"],
        casa=dados["casa"],
        squad=dados["squad"],
        acao=dados["acao"],
        janela_inicio=dados["janela_inicio"],
        janela_fim=dados["janela_fim"],
        segmentos=tuple(_le_segmento_risco(s) for s in dados["segmentos"]),
        cobertura_pct=_numero_de_dict(dados["cobertura_pct"], contexto="cobertura_pct"),
        cobertura_piso=_piso(dados["cobertura_piso"]),
        cobertura_ok=dados["cobertura_ok"],
        vies_selecao=_achado_unificado_de_dict(vies) if vies is not None else None,
        achados_governanca=tuple(
            _achado_unificado_de_dict(a) for a in dados["achados_governanca"]
        ),
        proveniencia=dados["proveniencia"],
    )


def eh_preflight(dados: dict[str, Any]) -> bool:
    """Distingue o envelope de grava_preflight (chave 'spec') do de
    grava_resultado (chave 'digest') sem depender de indentacao/ordem."""
    return "spec" in dados


def eh_risco(dados: dict[str, Any]) -> bool:
    """Distingue o envelope de grava_risco (chave 'risco') dos outros dois."""
    return "risco" in dados


def lista_resultados(saida: Path = SAIDA_PADRAO, *, desde: str | None = None) -> tuple[Path, ...]:
    """Arquivos gravados por grava_resultado, ordenados por tempo.

    desde filtra por gravado_em (ISO-8601 UTC compara igual a ordem
    temporal como string).
    """
    caminhos = sorted(saida.glob("*/*/*.json"))
    if desde is None:
        return tuple(caminhos)
    return tuple(
        c for c in caminhos if json.loads(c.read_text(encoding="utf-8"))["gravado_em"] >= desde
    )
