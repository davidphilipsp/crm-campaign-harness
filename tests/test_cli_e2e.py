"""Aceitacao: exercita harness.cli.main() de ponta a ponta (via sys.argv),
nao so build_parser() (tests/test_cli.py so testa parsing, nunca dispatch).

'ingest' agora roda harness.lint.runner.roda_lint e persiste o canal de
achados (achado 1 da auditoria fechado); 'lint' tem dispatch de verdade
(achado 2 fechado). 'verify' continua sem dispatch -- depende do ledger
append-only de M4, que ainda nao existe -- e fica xfail(strict=True) tanto
no teste dedicado quanto no caso parametrizado, para nao mascarar quando
esse dia chegar.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from harness.cli import build_parser, main
from harness.persist.resultados import lista_resultados

CAMINHO_GOLDEN_CSV = Path("tests/golden/demo_9000001/entrada.csv")
# CTOR (CLICK/IMPRESSION) desta fixture eh 0.90 (180 cliques / 200
# impressoes), acima do piso CTOR_MAX_ANOMALO=0.60 (harness/pisos.py) --
# gerada por tools/gera_golden.py (nao mais a fixture capturada com
# event_time identico em toda linha). Reusada aqui em vez de fixture
# sintetica propria: ja existe, ja e golden, e ja dispara o achado que o
# pipeline deveria persistir.


def test_ingest_deveria_persistir_achado_ctor_de_b3(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    saida = tmp_path / "resultados"
    argv = [
        "harness", "ingest", str(CAMINHO_GOLDEN_CSV),
        "--casa", "brand_a", "--campanha", "9000001", "--braco", "tratamento",
        "--de", "2026-07-01T00:00:00Z", "--ate", "2026-07-28T00:00:00Z",
        "--universo", "csv", "--hipotese", "oferta converte mais que a generica",
        "--saida", str(saida),
    ]
    monkeypatch.setattr(sys, "argv", argv)

    main()

    (caminho,) = lista_resultados(saida)
    dados = json.loads(caminho.read_text(encoding="utf-8"))

    assert "achados" in dados, (
        "grava_resultado (harness/persist/resultados.py) nao grava chave "
        "'achados' -- detecta_ctor_anomalo/detecta_optout_alto (B3) nunca "
        "sao chamados por roda_ingest (harness/cli.py)"
    )
    gates = {a["tipo"] for a in dados.get("achados", [])}
    assert "ctor_anomalo" in gates, (
        "fixture golden/demo_9000001 tem CTOR=0.90 > piso 0.60 "
        "(CTOR_MAX_ANOMALO) -- deveria ter disparado detecta_ctor_anomalo"
    )


def test_lint_nao_deveria_lancar_notimplementederror(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() agora tem branch para 'lint' (roda_lint_cli); roda sobre
    resultados/ padrao (nao existe neste checkout), entao levanta
    SemResultadoParaLint -- qualquer excecao serve aqui, contanto que nao
    seja mais o catch-all NotImplementedError que definia a lacuna."""
    monkeypatch.setattr(sys, "argv", ["harness", "lint"])

    levantou: BaseException | None = None
    try:
        main()
    except BaseException as exc:  # noqa: BLE001 -- queremos capturar qualquer excecao
        levantou = exc

    assert not isinstance(levantou, NotImplementedError), (
        "'harness lint' cai no catch-all NotImplementedError de main() -- "
        "subcomando documentado (tools.yaml) mas sem dispatch nem C1-C7"
    )


@pytest.mark.xfail(strict=True, reason="M4")
def test_verify_nao_deveria_lancar_notimplementederror(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mesma lacuna de 'lint', mas 'verify' (hash chain do ledger) depende do
    ledger append-only de M4 -- ainda nao existe, entao o xfail eh esperado
    e deve virar falha dura (XPASS) no dia em que M4 entregar o ledger."""
    monkeypatch.setattr(sys, "argv", ["harness", "verify"])

    levantou: BaseException | None = None
    try:
        main()
    except BaseException as exc:  # noqa: BLE001 -- queremos capturar qualquer excecao
        levantou = exc

    assert not isinstance(levantou, NotImplementedError), (
        "'harness verify' cai no catch-all NotImplementedError de main()"
    )


def _subcomandos() -> dict[str, argparse.ArgumentParser]:
    """Le os subcomandos direto do parser -- sem lista escrita a mao, entao
    um subparser novo sem dispatch em main() aparece aqui sozinho."""
    for action in build_parser()._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    raise AssertionError("build_parser() nao tem subparsers")


def _valor_dummy(action: argparse.Action) -> str:
    if action.choices:
        return str(sorted(action.choices)[0])
    return "1"


def _argv_minimo(nome: str, subparser: argparse.ArgumentParser) -> list[str]:
    argv = [nome]
    for action in subparser._actions:
        if isinstance(action, argparse._HelpAction) or not action.required:
            continue
        if action.option_strings:
            argv.append(action.option_strings[0])
        argv.append(_valor_dummy(action))
    return argv


SUBCOMANDOS = _subcomandos()


def _parametros_subcomando() -> list[Any]:
    """"verify" continua sem dispatch (M4, ledger append-only nao existe
    ainda) -- xfail(strict=True) documenta a lacuna conhecida em vez de
    reportar como falha vermelha comum, igual ao teste dedicado acima.
    "lint" NAO entra aqui: tem dispatch de verdade desde este commit."""
    return [
        pytest.param(nome, marks=pytest.mark.xfail(strict=True, reason="M4"))
        if nome == "verify"
        else nome
        for nome in sorted(SUBCOMANDOS)
    ]


@pytest.mark.parametrize("nome", _parametros_subcomando())
def test_todo_subcomando_tem_dispatch_em_main(
    nome: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Roda cada subcomando do parser com argumentos minimos (dummy, dados
    invalidos de proposito) e so verifica que main() nao cai no catch-all
    NotImplementedError. Qualquer outra excecao (arquivo inexistente, valor
    fora de faixa, git ausente) prova que o dispatch existe e ja executou
    logica real antes de falhar por motivo alheio a este teste."""
    monkeypatch.chdir(tmp_path)
    argv = ["harness", *_argv_minimo(nome, SUBCOMANDOS[nome])]
    monkeypatch.setattr(sys, "argv", argv)

    levantou: BaseException | None = None
    try:
        main()
    except BaseException as exc:  # noqa: BLE001 -- queremos capturar qualquer excecao
        levantou = exc

    assert not isinstance(levantou, NotImplementedError), (
        f"'{nome}' esta no parser mas cai no catch-all NotImplementedError "
        f"de main() -- subparser existe, dispatch nao"
    )
