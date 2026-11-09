"""P3: envio do documento ao consumidor downstream. Isolado do resto -- mesmo padrao do
driver de Postgres em ingest/pg/: o nucleo (documento.py, guarda.py) e
stdlib pura e testavel offline; rede e I/O, e I/O fica na borda.

Sem dependencia externa: urllib.request e stdlib e basta para um POST.
"""

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Protocol

_LIMITE_BYTES = 4 * 1024 * 1024

# explicito, nunca o default de urlopen (que espera para sempre sem timeout)
_TIMEOUT_S = 10.0


class VariavelDeAmbienteAusente(Exception):
    def __init__(self, variavel: str) -> None:
        super().__init__(f"variavel de ambiente ausente: {variavel}")


class DocumentoGrandeDemais(Exception):
    def __init__(self, tamanho: int) -> None:
        super().__init__(f"documento tem {tamanho} bytes, limite e {_LIMITE_BYTES}")


class FalhaNoEnvio(Exception):
    pass


def _env(nome: str) -> str:
    valor = os.environ.get(nome)
    if not valor:
        raise VariavelDeAmbienteAusente(nome)
    return valor


class RespostaHTTP(Protocol):
    def __enter__(self) -> "RespostaHTTP": ...
    def __exit__(self, *exc: object) -> None: ...
    def read(self) -> bytes: ...


Transporte = Callable[..., RespostaHTTP]


def publica(documento_json: bytes, *, transporte: Transporte | None = None) -> None:
    """POST do documento ja serializado. Teto de 4 MB verificado antes de
    qualquer I/O -- documento grande demais nunca chega a tentar a rede."""
    if len(documento_json) > _LIMITE_BYTES:
        raise DocumentoGrandeDemais(len(documento_json))

    url = _env("CONSUMER_URL")
    chave = _env("CONSUMER_HARNESS_KEY")

    req = urllib.request.Request(
        url,
        data=documento_json,
        headers={"X-Harness-Key": chave, "Content-Type": "application/json"},
        method="POST",
    )
    abrir: Transporte = transporte if transporte is not None else urllib.request.urlopen
    try:
        with abrir(req, timeout=_TIMEOUT_S) as resp:
            resp.read()
    except urllib.error.URLError as exc:
        raise FalhaNoEnvio(str(exc)) from exc


def serializa_documento(documento: dict[str, object]) -> bytes:
    return json.dumps(documento, sort_keys=True, ensure_ascii=False).encode("utf-8")
