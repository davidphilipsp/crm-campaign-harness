from collections.abc import Iterator

from harness.ingest.fonte import FonteZ0


class _Conforme:
    def linhas(self) -> Iterator[dict[str, str]]:
        return iter(())

    def proveniencia(self) -> dict[str, str]:
        return {"fonte": "teste"}


class _SemProveniencia:
    def linhas(self) -> Iterator[dict[str, str]]:
        return iter(())


def test_implementacao_completa_satisfaz_o_protocolo() -> None:
    assert isinstance(_Conforme(), FonteZ0)


def test_implementacao_incompleta_nao_satisfaz_o_protocolo() -> None:
    assert not isinstance(_SemProveniencia(), FonteZ0)
