"""F1: ingest roda C3/C2 e grava o veredito -- lints deixa de ser sempre {}."""

import json
from decimal import Decimal
from pathlib import Path

from harness.cli import build_parser, roda_ingest
from harness.contracts import Braco, Digest, EtapaFunil, Numero
from harness.lint import runner
from harness.lint.c3 import c3_entrega, entrega_comparavel
from harness.lint.contratos import AchadoUnificado, LintResult, ResultadoLint
from harness.lint.runner import roda_lint
from harness.persist.resultados import (
    grava_resultado,
    le_achados,
    le_c2,
    le_c3,
    le_gates,
    le_lint_resumo,
)
from harness.pisos import Piso
from harness.publica.documento import c2_dict, c3_dict

PISO_C3_PADRAO = Piso(Decimal("0.85"), "default_nao_validado")
PISO_C2_PADRAO = Piso(Decimal("0.05"), "default_nao_validado")

CASO = Path(__file__).parent / "golden" / "demo_9000001"
COLS = ("user_ext_id", "fact_type_id", "communication_id")
CAMINHO_ENTRADA = Path("tests/golden/demo_9000001/entrada.csv")


def _digest_um_braco() -> Digest:
    e = EtapaFunil("enviado", Numero(Decimal("1000"), "medido"))
    e2 = EtapaFunil("entregue", Numero(Decimal("500"), "medido"))
    return Digest(
        casa="brand_a", fase="leitura", universo="csv", campanha_id="x",
        janela_inicio="2026-01-01T00:00:00Z", janela_fim="2026-01-08T00:00:00Z",
        hipotese="h", contexto="", bracos=(Braco("tratamento", (e, e2)),),
        proveniencia={"fonte": "csv", "caminho": "x.csv", "sha256": "a" * 64},
    )


def _digest_dois_bracos() -> Digest:
    a = Braco("tratamento", (
        EtapaFunil("enviado", Numero(Decimal("1000"), "medido")),
        EtapaFunil("entregue", Numero(Decimal("950"), "medido")),
    ))
    b = Braco("comparacao", (
        EtapaFunil("enviado", Numero(Decimal("1000"), "medido")),
        EtapaFunil("entregue", Numero(Decimal("400"), "medido")),
    ))
    return Digest(
        casa="brand_a", fase="leitura", universo="csv", campanha_id="x",
        janela_inicio="2026-01-01T00:00:00Z", janela_fim="2026-01-08T00:00:00Z",
        hipotese="h", contexto="", bracos=(a, b),
        proveniencia={"fonte": "csv", "caminho": "x.csv", "sha256": "a" * 64},
    )


def test_c3_entrega_baixa_e_verde_com_achado_nunca_vermelho() -> None:
    d = _digest_um_braco()
    r = c3_entrega(d, piso=Piso(Decimal("0.85"), "default_nao_validado"))
    assert r.veredito == "verde"
    assert r.achados


def _resultado_lint(
    d: Digest, *, piso_c3: Piso = PISO_C3_PADRAO, piso_c2: Piso = PISO_C2_PADRAO
) -> ResultadoLint:
    return roda_lint(
        d, pisos={"C3_ENTREGA_MINIMA": piso_c3, "C2_DESVIO_MAX_BRACOS": piso_c2},
    )


def test_grava_resultado_lints_c3_bate_com_c3_dict(tmp_path: Path) -> None:
    """CRITERIO DE ACEITE: lints.c3 projetado do LintResult (via roda_lint)
    tem que sair byte a byte igual ao c3_dict(ResultadoC3) de antes -- C3
    calculado uma vez em roda_lint, c3_entrega aqui so gera o oraculo."""
    d = _digest_um_braco()
    r_c3 = c3_entrega(d, piso=PISO_C3_PADRAO)
    caminho = grava_resultado(d, saida=tmp_path, resultado_lint=_resultado_lint(d))
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados["lints"]["c3"] == c3_dict(r_c3)
    assert dados["lints"]["c3"]["veredito"] == "verde"


def test_grava_resultado_lints_c2_bate_com_c2_dict(tmp_path: Path) -> None:
    """Mesmo criterio para C2. C3 vem junto agora (REGISTRO roda os dois
    dentro do mesmo roda_lint) -- diferente do antigo c2=r_c2 isolado."""
    d = _digest_dois_bracos()
    piso_c2 = Piso(Decimal("0.05"), "crm_md")
    r_c2 = entrega_comparavel(d, piso=piso_c2)
    caminho = grava_resultado(
        d, saida=tmp_path, resultado_lint=_resultado_lint(d, piso_c2=piso_c2),
    )
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados["lints"]["c2"] == c2_dict(r_c2)
    assert "c3" in dados["lints"]


def test_le_c3_reconstroi_o_que_grava_resultado_escreveu(tmp_path: Path) -> None:
    d = _digest_um_braco()
    r_c3 = c3_entrega(d, piso=PISO_C3_PADRAO)
    caminho = grava_resultado(d, saida=tmp_path, resultado_lint=_resultado_lint(d))
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert le_c3(dados["lints"]["c3"]) == r_c3


def test_le_c2_reconstroi_o_que_grava_resultado_escreveu(tmp_path: Path) -> None:
    d = _digest_dois_bracos()
    piso_c2 = Piso(Decimal("0.05"), "crm_md")
    r_c2 = entrega_comparavel(d, piso=piso_c2)
    caminho = grava_resultado(
        d, saida=tmp_path, resultado_lint=_resultado_lint(d, piso_c2=piso_c2),
    )
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert le_c2(dados["lints"]["c2"]) == r_c2


def test_ida_e_volta_de_achado_c2_preserva_os_dois_bracos_na_ordem(tmp_path: Path) -> None:
    """AchadoUnificado.bracos: dois nomes para C2 (maior, menor de entrega),
    mesma ordem depois de gravar e reler -- e o campo que desbloqueou a
    unificacao (achado 1 do relatorio anterior)."""
    d = _digest_dois_bracos()
    piso_c2 = Piso(Decimal("0.01"), "crm_md")  # piso baixo: forca achado de C2
    resultado_lint = _resultado_lint(d, piso_c2=piso_c2)
    lr_c2 = next(lr for lr in resultado_lint.resultados if lr.gate == "C2")
    assert lr_c2.achados and lr_c2.achados[0].bracos == ("tratamento", "comparacao")

    caminho = grava_resultado(d, saida=tmp_path, resultado_lint=resultado_lint)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    reconstruido = le_c2(dados["lints"]["c2"])
    assert reconstruido.achados[0].bracos == ("tratamento", "comparacao")


def test_grava_resultado_sem_lints_continua_vazio(tmp_path: Path) -> None:
    caminho = grava_resultado(_digest_um_braco(), saida=tmp_path)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados["lints"] == {}


def test_le_achados_reconstroi_o_que_grava_resultado_escreveu(tmp_path: Path) -> None:
    d = _digest_um_braco()
    achados = (
        AchadoUnificado(
            origem="C3", resumo="entrega baixa", evidencia={"enviado": "1000"},
            bracos=("tratamento",),
        ),
        AchadoUnificado(origem="ctor_anomalo", resumo="ctor alto", evidencia={"<=0s": "12"}),
    )
    resultado_lint = ResultadoLint(veredito="vermelho", resultados=(), achados=achados)
    caminho = grava_resultado(d, saida=tmp_path, resultado_lint=resultado_lint)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert le_achados(dados["achados"]) == achados


def test_le_lint_resumo_reconstroi_o_que_grava_resultado_escreveu(tmp_path: Path) -> None:
    d = _digest_um_braco()
    gates_ausentes = ("C1", "C1-b", "C4", "C5", "C6", "C7")
    resultado_lint = ResultadoLint(
        veredito="vermelho",
        resultados=tuple(
            LintResult(gate=g, veredito="vermelho", motivo="gate_nao_implementado",
                       achados=(), piso_usado=None)
            for g in gates_ausentes
        ),
        achados=(),
    )
    caminho = grava_resultado(d, saida=tmp_path, resultado_lint=resultado_lint)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert le_lint_resumo(dados["lint"]) == ("vermelho", gates_ausentes)


def test_le_lint_resumo_e_none_quando_nao_gravado(tmp_path: Path) -> None:
    caminho = grava_resultado(_digest_um_braco(), saida=tmp_path)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados["lint"] is None
    assert le_lint_resumo(dados["lint"]) is None


def test_todo_gate_do_registro_aparece_no_json_persistido(tmp_path: Path) -> None:
    """Espelha test_todo_subcomando_tem_dispatch_em_main (tests/
    test_cli_e2e.py): introspecta runner.REGISTRO, sem lista escrita a
    mao -- gate novo que entre em REGISTRO sem ser persistido no canal
    generico "gates" quebra este teste sozinho, sem editar nada aqui."""
    d = _digest_um_braco()
    caminho = grava_resultado(d, saida=tmp_path, resultado_lint=_resultado_lint(d))
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    gates_persistidos = {g["gate"] for g in dados["gates"]}
    for nome_gate in runner.REGISTRO:
        assert nome_gate in gates_persistidos, (
            f"{nome_gate!r} esta em REGISTRO mas nao aparece em dados['gates']"
        )


def test_ida_e_volta_de_todo_lintresult_preserva_motivo(tmp_path: Path) -> None:
    """Os cinco campos de LintResult (gate, veredito, motivo, achados,
    piso_usado) sobrevivem ao ida-e-volta -- inclusive motivo, que nunca
    era persistido antes do canal generico "gates"."""
    d = _digest_dois_bracos()
    resultado_lint = _resultado_lint(d)
    caminho = grava_resultado(d, saida=tmp_path, resultado_lint=resultado_lint)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert le_gates(dados["gates"]) == resultado_lint.resultados


def test_roda_ingest_grava_c3_verde_com_achado_para_o_golden(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        [
            "ingest", str(CAMINHO_ENTRADA),
            "--casa", "brand_a", "--campanha", "9000001", "--braco", "tratamento",
            "--de", "2026-07-01T00:00:00Z", "--ate", "2026-07-28T00:00:00Z",
            "--universo", "csv", "--hipotese", "oferta converte mais que a generica",
            "--saida", str(tmp_path),
        ]
    )
    roda_ingest(args)
    (caminho,) = sorted(tmp_path.glob("*/*/*.json"))
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados["lints"]["c3"]["veredito"] == "verde"
    assert len(dados["lints"]["c3"]["achados"]) == 1
    assert dados["lints"]["c2"]["veredito"] == "indeterminado"

    # roda_lint reune o ROSTER inteiro -- vermelho por ausencia dos outros
    # 6 gates, mesmo com C3 verde e C2 indeterminado.
    assert dados["lint"]["veredito"] == "vermelho"
    assert set(dados["lint"]["gates_ausentes"]) == {"C1", "C1-b", "C4", "C5", "C6", "C7"}
    tipos = {a["tipo"] for a in dados["achados"]}
    assert "C3" in tipos
    assert "ctor_anomalo" in tipos
