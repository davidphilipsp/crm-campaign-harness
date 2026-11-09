import urllib.error
import urllib.request

import pytest

from harness.publica.envio import (
    DocumentoGrandeDemais,
    FalhaNoEnvio,
    VariavelDeAmbienteAusente,
    publica,
    serializa_documento,
)


class _RespostaFake:
    def __enter__(self) -> "_RespostaFake":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return b"ok"


class _TransporteFake:
    def __init__(self) -> None:
        self.chamado = False
        self.request: urllib.request.Request | None = None
        self.timeout: float | None = None

    def __call__(self, req: urllib.request.Request, *, timeout: float) -> _RespostaFake:
        self.chamado = True
        self.request = req
        self.timeout = timeout
        return _RespostaFake()


class _TransporteQueFalha:
    def __call__(self, req: urllib.request.Request, *, timeout: float) -> _RespostaFake:
        raise urllib.error.URLError("conexao recusada")


def test_publica_envia_com_headers_e_body_corretos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONSUMER_URL", "https://consumer.example/api/harness/resultados")
    monkeypatch.setenv("CONSUMER_HARNESS_KEY", "segredo")
    fake = _TransporteFake()

    publica(b'{"versao":1}', transporte=fake)

    assert fake.chamado
    assert fake.request is not None
    assert fake.request.full_url == "https://consumer.example/api/harness/resultados"
    assert fake.request.get_header("X-harness-key") == "segredo"
    assert fake.request.get_header("Content-type") == "application/json"
    assert fake.request.data == b'{"versao":1}'
    assert fake.timeout == 10.0


def test_publica_recusa_sem_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONSUMER_URL", raising=False)
    monkeypatch.setenv("CONSUMER_HARNESS_KEY", "segredo")
    fake = _TransporteFake()
    with pytest.raises(VariavelDeAmbienteAusente, match="CONSUMER_URL"):
        publica(b"{}", transporte=fake)
    assert not fake.chamado


def test_publica_recusa_sem_chave(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONSUMER_URL", "https://x")
    monkeypatch.delenv("CONSUMER_HARNESS_KEY", raising=False)
    fake = _TransporteFake()
    with pytest.raises(VariavelDeAmbienteAusente, match="CONSUMER_HARNESS_KEY"):
        publica(b"{}", transporte=fake)
    assert not fake.chamado


def test_publica_recusa_documento_grande_demais_sem_tentar_rede(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CONSUMER_URL", raising=False)
    monkeypatch.delenv("CONSUMER_HARNESS_KEY", raising=False)
    fake = _TransporteFake()
    grande = b"x" * (4 * 1024 * 1024 + 1)
    with pytest.raises(DocumentoGrandeDemais):
        publica(grande, transporte=fake)
    assert not fake.chamado


def test_publica_propaga_erro_http_como_falha_no_envio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONSUMER_URL", "https://x")
    monkeypatch.setenv("CONSUMER_HARNESS_KEY", "segredo")
    with pytest.raises(FalhaNoEnvio):
        publica(b"{}", transporte=_TransporteQueFalha())


def test_serializa_documento_e_bytes_json() -> None:
    saida = serializa_documento({"versao": 1, "a": "b"})
    assert saida == b'{"a": "b", "versao": 1}'
