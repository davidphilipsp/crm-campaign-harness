import argparse

from harness.casas import casas_validas


class SemResultadoParaLint(Exception):
    """'harness lint' precisa de ao menos um resultado de leitura gravado
    (harness ingest) em --entrada -- sem isso nao ha digest para reler."""


class ParametroMalFormado(Exception):
    """'harness query' exige --param no formato chave=valor."""

    def __init__(self, item: str) -> None:
        super().__init__(f"--param mal formado, esperado chave=valor: {item!r}")


class ParametrosDivergentes(Exception):
    """'harness query' recusa rodar com params faltando ou sobrando --
    nunca deixa a query executar com um subconjunto silencioso."""

    def __init__(self, nome: str, esperados: set[str], fornecidos: set[str]) -> None:
        faltando = sorted(esperados - fornecidos)
        sobrando = sorted(fornecidos - esperados)
        super().__init__(
            f"query {nome!r} espera params {sorted(esperados)}, recebeu {sorted(fornecidos)} "
            f"(faltando={faltando}, sobrando={sobrando})"
        )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="harness")
    sub = p.add_subparsers(dest="comando", required=True)
    p_ing = sub.add_parser("ingest", help="Z0 -> Z1: le CSV, produz digest")
    p_ing.add_argument("csv", help="caminho do export (Z0, fora do repo)")
    p_ing.add_argument("--casa", required=True, choices=sorted(casas_validas()))
    p_ing.add_argument("--campanha", required=True)
    p_ing.add_argument("--braco", required=True,
                       choices=["holdout", "comparacao", "tratamento"])
    p_ing.add_argument("--de", required=True, help="ISO-8601 UTC")
    p_ing.add_argument("--ate", required=True, help="ISO-8601 UTC")
    p_ing.add_argument("--universo", required=True, choices=["state", "behaviour", "csv"])
    p_ing.add_argument("--hipotese", required=True, help="ex-ante, obrigatoria (C7)")
    p_ing.add_argument("--contexto", default="")
    p_ing.add_argument("--saida", default="resultados", help="raiz dos resultados gravados")

    p_pre = sub.add_parser("preflight", help="roda C8, C9, C11 sobre uma SpecCampanha")
    p_pre.add_argument("--casa", required=True, choices=sorted(casas_validas()))
    p_pre.add_argument("--universo", required=True, choices=["state", "behaviour", "csv"])
    p_pre.add_argument("--regua", required=True)
    p_pre.add_argument("--base-estimada", required=True, type=int)
    p_pre.add_argument("--pct-holdout", required=True, help="Decimal, ex: 0.05")
    p_pre.add_argument("--conversao-esperada", required=True, help="Decimal, ex: 0.03")
    p_pre.add_argument("--fonte-conversao-controle", required=True,
                       choices=["no_flow", "evento_atribuido", "ausente"])
    p_pre.add_argument("--max-duration-s", required=True, type=int)
    p_pre.add_argument("--delays-s", required=True, help="lista separada por virgula, ex: 60,3600")
    # sem default: piso_mde_ok nao tem tabela de default nem linha em CRM.md
    # (harness.pisos) -- parametro obrigatorio, como esta (NAO CONSTRUA).
    p_pre.add_argument("--piso-mde-ok", required=True, help="Decimal, ex: 0.25")
    p_pre.add_argument("--saida", default="resultados", help="raiz dos resultados gravados")

    p_lint = sub.add_parser("lint", help="roda o ROSTER de gates + detectores B sobre um digest")
    p_lint.add_argument("--entrada", default="resultados", help="raiz dos resultados gravados")
    sub.add_parser("verify", help="verifica a hash chain do ledger")
    sub.add_parser("docs", help="regenera a tabela do SKILL.md a partir de tools.yaml")
    p_pub = sub.add_parser("publica", help="monta o documento e publica no consumidor downstream")
    p_pub.add_argument("--entrada", default="resultados", help="raiz dos resultados gravados")
    p_pub.add_argument("--desde", default=None,
                       help="ISO-8601 UTC; so publica resultados a partir daqui")
    p_pub.add_argument("--dry-run", action="store_true",
                       help="monta, passa pelo guarda, imprime tamanho e NAO envia")

    p_query = sub.add_parser(
        "query",
        help="roda uma query nomeada do catalogo (E8) contra a replica Postgres de uma "
             "casa -- reporte de risco/financeiro; nunca grava em resultados/ nem alimenta "
             "'harness publica' (E22)",
    )
    p_query.add_argument("nome", help="nome da query em harness/ingest/queries/")
    p_query.add_argument("--casa", required=True, choices=sorted(casas_validas()))
    p_query.add_argument(
        "--param", action="append", default=[], metavar="chave=valor",
        help="repetivel; deve cobrir exatamente os params declarados no cabecalho da query",
    )
    p_query.add_argument("--formato", choices=["csv", "json"], default="csv")
    p_query.add_argument("--saida", default=None, help="caminho de saida; default stdout")

    p_risco = sub.add_parser(
        "risco",
        help="ingere o resumo estruturado que um risk squad produziu ao final de "
             "uma analise (E23) -- o harness nunca chama MCP nem roda SQL, so valida "
             "o contrato, aplica o piso de cobertura e grava para 'harness publica' ler",
    )
    p_risco.add_argument("arquivo", help="JSON com o veredito do squad (autodescritivo)")
    p_risco.add_argument("--saida", default="resultados", help="raiz dos resultados gravados")
    return p


def main() -> None:
    args = build_parser().parse_args()
    if args.comando == "ingest":
        roda_ingest(args)
        return
    if args.comando == "preflight":
        roda_preflight(args)
        return
    if args.comando == "lint":
        roda_lint_cli(args)
        return
    if args.comando == "publica":
        roda_publica(args)
        return
    if args.comando == "query":
        roda_query(args)
        return
    if args.comando == "risco":
        roda_risco(args)
        return
    if args.comando == "docs":
        gera_docs()
        return
    raise NotImplementedError(args.comando)


def gera_docs() -> None:
    from pathlib import Path

    from harness.docs import gera

    gera(Path("tools.yaml"), Path("SKILL.md"))


def roda_ingest(args: argparse.Namespace) -> None:
    from pathlib import Path

    from harness.digest import digest_hash
    from harness.ingest.agrega import monta_digest
    from harness.ingest.fonte_csv import FonteCSV
    from harness.lint.runner import DETECTORES, roda_lint
    from harness.persist.resultados import grava_resultado
    from harness.pisos import carrega_piso

    fonte = FonteCSV(
        Path(args.csv),
        colunas_esperadas=("user_ext_id", "fact_type_id", "communication_id"),
    )
    d = monta_digest(
        fonte,
        braco=args.braco,
        casa=args.casa,
        universo=args.universo,
        campanha_id=args.campanha,
        janela_inicio=args.de,
        janela_fim=args.ate,
        hipotese=args.hipotese,
        contexto=args.contexto,
    )
    for b in d.bracos:
        for e in b.etapas:
            print(f"{b.nome:12} {e.nome:10} {e.volume.valor} [{e.volume.rotulo}]")
    print(f"digest_hash: {digest_hash(d.como_dict())}")

    # CLI resolve os pisos e injeta -- gate nunca carrega piso por dentro.
    # roda_lint e o unico lugar que calcula C3/C2 (harness/lint/runner.py) --
    # sem chamada direta a c3_entrega/entrega_comparavel aqui, so a leitura
    # do LintResult correspondente para o print de resumo abaixo.
    pisos = {
        "C3_ENTREGA_MINIMA": carrega_piso("C3_ENTREGA_MINIMA"),
        "C2_DESVIO_MAX_BRACOS": carrega_piso("C2_DESVIO_MAX_BRACOS"),
        "CTOR_MAX_ANOMALO": carrega_piso("CTOR_MAX_ANOMALO"),
        # sem "piso_optout": nenhum default sancionado em harness.pisos --
        # optout_alto fica pendente (print abaixo), nunca inventado aqui.
    }
    resultado_lint = roda_lint(d, pisos=pisos)
    for lr in resultado_lint.resultados:
        if lr.gate in ("C3", "C2", "C6-ordem"):
            print(f"{lr.gate} ({lr.motivo}): {lr.veredito}, {len(lr.achados)} achado(s)")
    print(f"lint: {resultado_lint.veredito} ({len(resultado_lint.achados)} achado(s))")
    for spec in DETECTORES:
        if spec.piso_chave not in pisos:
            print(f"  {spec.nome}: pendente (sem piso {spec.piso_chave!r})")
        elif spec.dado_ausente(d):
            print(f"  {spec.nome}: nao-executavel (dado ausente no digest)")

    caminho = grava_resultado(d, saida=Path(args.saida), resultado_lint=resultado_lint)
    print(f"gravado: {caminho}")


def roda_preflight(args: argparse.Namespace) -> None:
    from decimal import Decimal
    from pathlib import Path

    from harness.persist.resultados import grava_preflight
    from harness.pisos import Piso, carrega_piso
    from harness.preflight import (
        SpecCampanha,
        avalia_duracao_vs_delays,
        avalia_fonte_conversao_controle,
        avalia_mde_vs_base,
    )

    delays = tuple(int(x) for x in args.delays_s.split(","))
    spec = SpecCampanha(
        fase="preflight",
        casa=args.casa,
        universo=args.universo,
        regua=args.regua,
        base_estimada=args.base_estimada,
        pct_holdout=Decimal(args.pct_holdout),
        conversao_esperada=Decimal(args.conversao_esperada),
        fonte_conversao_controle=args.fonte_conversao_controle,
        max_duration_s=args.max_duration_s,
        delays_s=delays,
    )

    # CLI resolve os pisos e injeta -- gate nunca carrega piso por dentro.
    # piso_amostra tem default versionado (harness.pisos); piso_mde_ok nao
    # tem -- operador declara na linha de comando, origem "cli" (E17b).
    piso_amostra = carrega_piso("C_AMOSTRA_MIN_CONTRASTE")
    piso_mde_ok = Piso(Decimal(args.piso_mde_ok), "cli")

    c8 = avalia_mde_vs_base(spec, piso_amostra=piso_amostra, piso_mde_ok=piso_mde_ok)
    c9 = avalia_fonte_conversao_controle(spec)
    c11 = avalia_duracao_vs_delays(spec)

    print(f"c8: {c8.veredito}  n_holdout={c8.n_holdout} n_tratamento={c8.n_tratamento}")
    print(f"c9: {'aprova' if c9.aprova else 'reprova'}  {c9.motivo}")
    print(f"c11: {'aprova' if c11.aprova else 'reprova'}  {c11.motivo}")

    caminho = grava_preflight(spec, saida=Path(args.saida), c8=c8, c9=c9, c11=c11)
    print(f"gravado: {caminho}")


def roda_lint_cli(args: argparse.Namespace) -> None:
    """'harness lint': recarrega o ultimo resultado de leitura gravado e
    roda roda_lint sobre o Digest reconstruido. Sem `linhas` (dado bruto
    Z0) -- um digest relido do disco nao carrega linha a linha, entao so
    os gates do ROSTER rodam aqui, nunca os detectores B (ver docstring de
    roda_lint em harness/lint/runner.py). Hoje isso da vermelho por
    ausencia de 6 dos 8 gates -- esperado, nao e regressao."""
    import json
    from pathlib import Path

    from harness.lint.runner import DETECTORES, roda_lint
    from harness.persist.resultados import eh_preflight, eh_risco, le_digest, lista_resultados
    from harness.pisos import carrega_piso

    leituras = []
    for caminho in lista_resultados(Path(args.entrada)):
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        if not eh_preflight(dados) and not eh_risco(dados):
            leituras.append(dados)
    if not leituras:
        raise SemResultadoParaLint(
            f"nenhum resultado de leitura em {args.entrada!r} -- rode 'harness ingest' primeiro"
        )

    digest = le_digest(leituras[-1]["digest"])
    pisos = {
        "C3_ENTREGA_MINIMA": carrega_piso("C3_ENTREGA_MINIMA"),
        "C2_DESVIO_MAX_BRACOS": carrega_piso("C2_DESVIO_MAX_BRACOS"),
        "CTOR_MAX_ANOMALO": carrega_piso("CTOR_MAX_ANOMALO"),
    }
    resultado = roda_lint(digest, pisos=pisos)

    print(f"lint: {resultado.veredito} ({len(resultado.achados)} achado(s))")
    for lr in resultado.resultados:
        print(f"  {lr.gate}: {lr.veredito} ({lr.motivo})")
    for spec in DETECTORES:
        if spec.piso_chave not in pisos:
            print(f"  {spec.nome}: pendente (sem piso {spec.piso_chave!r})")
        elif spec.dado_ausente(digest):
            print(f"  {spec.nome}: nao-executavel (dado ausente no digest)")


def roda_publica(args: argparse.Namespace) -> None:
    import json
    import subprocess
    from datetime import UTC, datetime
    from pathlib import Path

    from harness.lint.achados import Achado as AchadoLint
    from harness.lint.runner import ROSTER
    from harness.persist.resultados import (
        eh_preflight,
        eh_risco,
        le_achados,
        le_c2,
        le_c3,
        le_c8,
        le_digest,
        le_risco,
        le_spec,
        le_veredicto_preflight,
        lista_resultados,
    )
    from harness.publica.documento import (
        ResultadoLeitura,
        ResultadoPreflight,
        ResultadoRisco,
        monta_documento,
    )
    from harness.publica.envio import publica as envia_documento
    from harness.publica.envio import serializa_documento
    from harness.publica.guarda import varre_documento

    caminhos = lista_resultados(Path(args.entrada), desde=args.desde)
    preflights = []
    leituras = []
    riscos = []
    for caminho in caminhos:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        if eh_preflight(dados):
            spec = le_spec(dados["spec"])
            preflights.append(
                ResultadoPreflight(
                    casa=spec.casa,
                    universo=spec.universo,
                    regua=spec.regua,
                    base_estimada=spec.base_estimada,
                    pct_holdout=spec.pct_holdout,
                    conversao_esperada=spec.conversao_esperada,
                    c8=le_c8(dados["c8"]) if dados.get("c8") is not None else None,
                    c9=le_veredicto_preflight(dados["c9"]) if dados.get("c9") is not None else None,
                    c11=(
                        le_veredicto_preflight(dados["c11"])
                        if dados.get("c11") is not None
                        else None
                    ),
                )
            )
            continue

        if eh_risco(dados):
            v = le_risco(dados["risco"])
            riscos.append(
                ResultadoRisco(
                    casa=v.casa,
                    squad=v.squad,
                    acao=v.acao,
                    janela_inicio=v.janela_inicio,
                    janela_fim=v.janela_fim,
                    segmentos=v.segmentos,
                    cobertura_pct=v.cobertura_pct,
                    cobertura_piso=v.cobertura_piso,
                    cobertura_ok=v.cobertura_ok,
                    vies_selecao=v.vies_selecao,
                    achados_governanca=v.achados_governanca,
                )
            )
            continue

        d = le_digest(dados["digest"])
        lints = dados.get("lints", {})
        # so achado de detector B entra no campo `achados` do documento --
        # achado de gate C ja tem representacao propria em c3/c2 (braco,
        # Decimal). origem que nao e nome de gate do ROSTER e, por
        # definicao, nome de detector (harness/lint/runner.py DETECTORES).
        achados = tuple(
            AchadoLint(
                tipo=a.origem,
                resumo=a.resumo,
                evidencia={chave: int(valor) for chave, valor in a.evidencia.items()},
            )
            for a in le_achados(dados.get("achados", []))
            if a.origem not in ROSTER
        )
        leituras.append(
            ResultadoLeitura(
                casa=d.casa,
                universo=d.universo,
                campanha_id=d.campanha_id,
                janela_inicio=d.janela_inicio,
                janela_fim=d.janela_fim,
                hipotese=d.hipotese,
                contexto=d.contexto,
                digest_hash=dados["digest_hash"],
                bracos=d.bracos,
                c3=le_c3(lints["c3"]) if "c3" in lints else None,
                c2=le_c2(lints["c2"]) if "c2" in lints else None,
                achados=achados,
            )
        )

    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    gerado_em = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    documento = monta_documento(
        preflights=tuple(preflights), leituras=tuple(leituras), riscos=tuple(riscos),
        gerado_em=gerado_em, harness_commit=commit,
    )
    varre_documento(documento)
    corpo = serializa_documento(documento)

    if args.dry_run:
        print(
            f"dry-run: {len(preflights)} preflights, {len(leituras)} leituras, "
            f"{len(riscos)} riscos, {len(corpo)} bytes, nao enviado"
        )
        return

    envia_documento(corpo)
    print(
        f"publicado: {len(preflights)} preflights, {len(leituras)} leituras, "
        f"{len(riscos)} riscos, {len(corpo)} bytes"
    )


def _parse_params(itens: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for item in itens:
        if "=" not in item:
            raise ParametroMalFormado(item)
        chave, _, valor = item.partition("=")
        params[chave] = valor
    return params


def roda_query(args: argparse.Namespace) -> None:
    """'harness query': roda uma query nomeada do catalogo (E8) contra a
    replica Postgres de uma casa. Reporte de risco/financeiro para o squad
    que ja consumia esse dado direto do Postgres -- nunca grava em
    resultados/ nem passa por harness publica (E22, fronteira de
    confianca: sem id_anon aqui, ver harness/relatorio/formata.py).

    Toda validacao (nome de query, params completos) acontece antes de
    tocar driver, credencial ou rede -- mesmo padrao de envio.py (teto de
    bytes antes do POST) e catalogo.py (params batem antes de carregar).
    """
    from pathlib import Path

    from harness.ingest.catalogo import carrega_por_nome
    from harness.ingest.pg import FontePostgres
    from harness.relatorio.formata import formata_csv, formata_json

    query = carrega_por_nome(args.nome)
    params = _parse_params(args.param)

    esperados, fornecidos = set(query.params), set(params)
    if fornecidos != esperados:
        raise ParametrosDivergentes(query.nome, esperados, fornecidos)

    fonte = FontePostgres(casa=args.casa, query=query, params=params)
    linhas = list(fonte.linhas())

    if args.formato == "csv":
        corpo = formata_csv(linhas)
    else:
        corpo = formata_json(linhas, proveniencia=fonte.proveniencia())

    if args.saida:
        Path(args.saida).write_text(corpo, encoding="utf-8")
        print(f"gravado: {args.saida} ({len(linhas)} linha(s))")
    else:
        print(corpo)


def roda_risco(args: argparse.Namespace) -> None:
    """'harness risco': ingere o resumo estruturado que um risk squad
    (brand-a-risk-squad, brand-b-financial-squad) produziu ao final da propria
    analise (E23). O harness nunca chama MCP nem roda SQL aqui -- so valida
    o contrato (harness.risco.ingestao), aplica o piso de cobertura
    (COBERTURA_MIN_DADO) e grava em resultados/ para 'harness publica' ler.
    """
    from pathlib import Path

    from harness.persist.resultados import grava_risco
    from harness.risco.ingestao import ingere

    veredicto = ingere(Path(args.arquivo))
    print(f"squad={veredicto.squad} casa={veredicto.casa} acao={veredicto.acao}")
    status = "ok" if veredicto.cobertura_ok else "suspenso (abaixo do piso ou ausente)"
    cobertura = (
        f"{veredicto.cobertura_pct.valor} ({veredicto.cobertura_pct.rotulo})"
        if veredicto.cobertura_pct.valor is not None
        else f"ausente ({veredicto.cobertura_pct.rotulo})"
    )
    print(
        f"cobertura={cobertura} "
        f"piso={veredicto.cobertura_piso.valor} ({veredicto.cobertura_piso.origem}) -> {status}"
    )

    caminho = grava_risco(veredicto, saida=Path(args.saida))
    print(f"gravado: {caminho}")


if __name__ == "__main__":
    main()
