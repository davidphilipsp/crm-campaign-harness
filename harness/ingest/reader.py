import csv
import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

from harness.ingest.pii_guard import AchadoPII, PIIEncontrada, varre_linha

_MESES = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

_EVENT_TIME = re.compile(
    r"^[A-Za-z]{3} (?P<mes>[A-Za-z]{3}) (?P<dia>\d{1,2}) (?P<ano>\d{4}) "
    r"(?P<hh>\d{2}):(?P<mi>\d{2}):(?P<ss>\d{2}) GMT(?P<sinal>[+-])(?P<off>\d{1,4})$"
)


def iso_utc(valor: str) -> str:
    """Converte o formato do Smartico para ISO-8601 UTC. Sem locale (RNF-02)."""
    m = _EVENT_TIME.match(valor.strip())
    if m is None:
        forma = re.sub(r"\d", "N", re.sub(r"[A-Za-z]", "A", valor.strip()))
        raise ValueError(f"event_time em formato desconhecido: {forma!r}")

    mes = _MESES.get(m.group("mes"))
    if mes is None:
        raise ValueError(f"mes desconhecido: {m.group('mes')!r}")

    off = m.group("off")
    if len(off) <= 2:
        horas, minutos = int(off), 0
    elif len(off) == 4:
        horas, minutos = int(off[:2]), int(off[2:])
    else:
        raise ValueError(f"offset de fuso ambiguo: {off!r}")

    sinal = 1 if m.group("sinal") == "+" else -1
    dt = datetime(
        int(m.group("ano")), mes, int(m.group("dia")),
        int(m.group("hh")), int(m.group("mi")), int(m.group("ss")),
        tzinfo=UTC,
    ) - sinal * timedelta(hours=horas, minutes=minutos)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _linhas(
    caminho: Path, colunas_esperadas: tuple[str, ...] | None = None
) -> Iterator[tuple[int, dict[str, str]]]:
    with caminho.open(newline="", encoding="utf-8-sig") as f:
        leitor = csv.reader(f)
        cabecalho = next(leitor, None)
        if cabecalho is None:
            raise ValueError(f"{caminho}: csv vazio")
        if len(cabecalho) == 1 and any(c in cabecalho[0] for c in ";\t|"):
            raise ValueError(
                f"{caminho}: cabecalho com uma coluna so contendo separador "
                f"alternativo; delimitador esperado e virgula"
            )
        if colunas_esperadas is not None:
            faltando = set(colunas_esperadas) - set(cabecalho)
            if faltando:
                raise ValueError(
                    f"{caminho}: colunas ausentes: {sorted(faltando)}"
                )
        for n, campos in enumerate(leitor, 1):
            if len(campos) != len(cabecalho):
                raise ValueError(
                    f"linha {n}: {len(campos)} campos, cabecalho tem {len(cabecalho)}"
                )
            yield n, dict(zip(cabecalho, campos, strict=True))


def _varre(caminho: Path, colunas_esperadas: tuple[str, ...] | None) -> None:
    achados: list[AchadoPII] = []
    for n, linha in _linhas(caminho, colunas_esperadas):
        achados.extend(varre_linha(n, linha))
    if achados:
        raise PIIEncontrada(tuple(achados))


def le_csv(
    caminho: Path, colunas_esperadas: tuple[str, ...] | None = None
) -> Iterator[dict[str, str]]:
    """Passada 1 recusa; passada 2 emite. Nada sai antes do arquivo estar limpo."""
    _varre(caminho, colunas_esperadas)
    return (linha for _, linha in _linhas(caminho, colunas_esperadas))
