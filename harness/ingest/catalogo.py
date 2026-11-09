"""Catalogo de queries parametrizadas: dado, nao codigo (E3, CRM.md).

O modelo escolhe QUAL pergunta -- o nome da query. O codigo decide COMO se
calcula. SQL do modelo tornaria o numero probabilistico e mataria RNF-01/02
(voce nao reconstroi a decisao de seis meses atras porque nao sabe qual
query rodou). Nada aqui executa nem conecta a banco nenhum.
"""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

DIRETORIO_PADRAO = Path(__file__).resolve().parent / "queries"

_CAMPOS_OBRIGATORIOS = ("nome", "params", "devolve")
_CABECALHO = re.compile(r"^-- (?P<chave>[a-z_]+): ?(?P<valor>.*)$")
_PARAM_NO_SQL = re.compile(r"%\((\w+)\)s")


@dataclass(frozen=True)
class QueryNomeada:
    nome: str
    sql: str
    params: tuple[str, ...]
    sha256: str


def carrega(caminho: Path) -> QueryNomeada:
    linhas = caminho.read_text(encoding="utf-8").splitlines()

    campos: dict[str, str] = {}
    fim_cabecalho: int | None = None
    for n, linha in enumerate(linhas):
        if not linha.startswith("--"):
            fim_cabecalho = n
            break
        m = _CABECALHO.match(linha)
        if m is None:
            raise ValueError(f"{caminho}: linha {n + 1} de cabecalho mal formada: {linha!r}")
        campos[m.group("chave")] = m.group("valor").strip()

    if fim_cabecalho is None:
        raise ValueError(f"{caminho}: arquivo so tem cabecalho, sem corpo de query")

    faltando = [c for c in _CAMPOS_OBRIGATORIOS if c not in campos]
    if faltando:
        raise ValueError(f"{caminho}: cabecalho sem campo(s) obrigatorio(s): {faltando}")

    nome = campos["nome"]
    if nome != caminho.stem:
        raise ValueError(
            f"{caminho}: nome declarado {nome!r} nao bate com o arquivo {caminho.stem!r}"
        )

    params = tuple(p.strip() for p in campos["params"].split(",") if p.strip())

    corpo = "\n".join(linhas[fim_cabecalho:]).strip()
    if not corpo:
        raise ValueError(f"{caminho}: corpo de query vazio")

    usados = set(_PARAM_NO_SQL.findall(corpo))
    declarados = set(params)
    if usados != declarados:
        raise ValueError(
            f"{caminho}: params declarados {sorted(declarados)} nao batem com os "
            f"usados no SQL {sorted(usados)} "
            f"(no sql sem declarar: {sorted(usados - declarados)}, "
            f"declarados sem uso: {sorted(declarados - usados)})"
        )

    return QueryNomeada(
        nome=nome,
        sql=corpo,
        params=params,
        sha256=hashlib.sha256(corpo.encode("utf-8")).hexdigest(),
    )


def carrega_por_nome(nome: str, *, diretorio: Path = DIRETORIO_PADRAO) -> QueryNomeada:
    caminho = diretorio / f"{nome}.sql"
    if not caminho.exists():
        raise ValueError(f"query desconhecida: {nome!r} (nao existe {caminho})")
    return carrega(caminho)
