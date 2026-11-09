from decimal import Decimal

import pytest

from harness.contracts import Braco, Digest, EtapaFunil, Numero

INI = "2026-07-01T00:00:00Z"
FIM = "2026-07-08T00:00:00Z"


def _braco(nome: str = "controle") -> Braco:
    e = EtapaFunil("enviado", Numero(Decimal("1000"), "medido"))
    return Braco(nome, (e,))  # type: ignore[arg-type]


def test_digest_valido() -> None:
    d = Digest(
        casa="brand_a",
        fase="leitura",
        universo="csv",
        campanha_id="C-42",
        janela_inicio=INI,
        janela_fim=FIM,
        hipotese="oferta converte mais que generica",
        contexto="",
        bracos=(_braco(),), proveniencia={"fonte": "teste"})
    assert d.casa == "brand_a"


def test_recusa_bracos_vazio() -> None:
    with pytest.raises(ValueError):
        Digest(
        casa="brand_a",
        fase="leitura",
        universo="csv",
        campanha_id="C-42",
        janela_inicio=INI,
        janela_fim=FIM,
        hipotese="oferta converte mais que generica",
        contexto="",
        bracos=(), proveniencia={"fonte": "teste"})


def test_recusa_braco_duplicado() -> None:
    b = _braco()
    with pytest.raises(ValueError):
        Digest(
        casa="brand_a",
        fase="leitura",
        universo="csv",
        campanha_id="C-42",
        janela_inicio=INI,
        janela_fim=FIM,
        hipotese="oferta converte mais que generica",
        contexto="",
        bracos=(b, b), proveniencia={"fonte": "teste"})


def test_recusa_janela_invertida() -> None:
    with pytest.raises(ValueError):
        Digest(
        casa="brand_a",
        fase="leitura",
        universo="csv",
        campanha_id="C-42",
        janela_inicio=FIM,
        janela_fim=INI,
        hipotese="oferta converte mais que generica",
        contexto="",
        bracos=(_braco(),), proveniencia={"fonte": "teste"})


def test_recusa_janela_de_duracao_zero() -> None:
    with pytest.raises(ValueError):
        Digest(
        casa="brand_a",
        fase="leitura",
        universo="csv",
        campanha_id="C-42",
        janela_inicio=INI,
        janela_fim=INI,
        hipotese="oferta converte mais que generica",
        contexto="",
        bracos=(_braco(),), proveniencia={"fonte": "teste"})


def test_casas_distintas_nao_colidem() -> None:
    brand_a = Digest(
        casa="brand_a",
        fase="leitura",
        universo="csv",
        campanha_id="C-42",
        janela_inicio=INI,
        janela_fim=FIM,
        hipotese="oferta converte mais que generica",
        contexto="",
        bracos=(_braco(),), proveniencia={"fonte": "teste"})
    brand_b = Digest(
        casa="brand_b",
        fase="leitura",
        universo="csv",
        campanha_id="C-42",
        janela_inicio=INI,
        janela_fim=FIM,
        hipotese="oferta converte mais que generica",
        contexto="",
        bracos=(_braco(),), proveniencia={"fonte": "teste"})
    assert brand_a != brand_b


def test_holdout_e_comparacao_sao_bracos_distintos() -> None:
    e = EtapaFunil("enviado", Numero(Decimal("100"), "medido"))
    d = Digest(
        casa="brand_a",
        fase="leitura",
        universo="csv",
        campanha_id="9000001",
        janela_inicio=INI,
        janela_fim=FIM,
        hipotese="oferta converte mais que generica",
        contexto="",
        bracos=(Braco("tratamento", (e,)), Braco("comparacao", (e,))),
        proveniencia={"fonte": "teste"},
    )
    assert {b.nome for b in d.bracos} == {"tratamento", "comparacao"}
    assert not any(b.nome == "holdout" for b in d.bracos)


def test_recusa_hipotese_vazia() -> None:
    e = EtapaFunil("enviado", Numero(Decimal("100"), "medido"))
    with pytest.raises(ValueError):
        Digest(
            casa="brand_a",
            fase="leitura",
            universo="csv",
            campanha_id="9000001",
            janela_inicio=INI,
            janela_fim=FIM,
            hipotese="   ",
            contexto="rodada habitual de sabado",
            bracos=(Braco("tratamento", (e,)),),
            proveniencia={"fonte": "teste"},
        )


def test_digest_recusa_fase_preflight() -> None:
    e = EtapaFunil("enviado", Numero(Decimal("100"), "medido"))
    with pytest.raises(ValueError):
        Digest(
            casa="brand_a",
            fase="preflight",
            universo="csv",
            campanha_id="9000001",
            janela_inicio=INI,
            janela_fim=FIM,
            hipotese="oferta converte mais que generica",
            contexto="",
            bracos=(Braco("tratamento", (e,)),),
            proveniencia={"fonte": "teste"},
        )


def test_hipotese_diferente_muda_o_hash() -> None:
    from harness.digest import digest_hash

    e = EtapaFunil("enviado", Numero(Decimal("100"), "medido"))
    base = {
        "casa": "brand_a",
        "fase": "leitura",
        "universo": "csv",
        "campanha_id": "9000001",
        "janela_inicio": INI,
        "janela_fim": FIM,
        "contexto": "",
        "bracos": (Braco("tratamento", (e,)),),
        "proveniencia": {"fonte": "teste"},
    }
    a = Digest(**base, hipotese="oferta converte mais")  # type: ignore[arg-type]
    b = Digest(**base, hipotese="oferta converte menos")  # type: ignore[arg-type]
    assert digest_hash(a.como_dict()) != digest_hash(b.como_dict())
