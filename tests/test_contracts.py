from decimal import Decimal

import pytest

from harness.contracts import Braco, EtapaFunil, Numero


def test_medido_com_valor() -> None:
    assert Numero(Decimal("0.61"), "medido").valor == Decimal("0.61")


def test_ausente_sem_valor() -> None:
    assert Numero(None, "ausente").valor is None


@pytest.mark.parametrize(
    ("valor", "rotulo"),
    [
        (Decimal("0"), "ausente"),
        (None, "medido"),
        (None, "estimado"),
    ],
)
def test_combinacao_proibida(valor: Decimal | None, rotulo: str) -> None:
    with pytest.raises(ValueError):
        Numero(valor, rotulo)  # type: ignore[arg-type]


def test_frozen_recusa_reatribuicao() -> None:
    n = Numero(Decimal("1"), "medido")
    with pytest.raises(AttributeError):
        n.valor = Decimal("2")  # type: ignore[misc]


def test_braco_hashavel() -> None:
    e = EtapaFunil("enviado", Numero(Decimal("1000"), "medido"))
    assert isinstance(hash(Braco("tratamento", (e,))), int)


def test_braco_recusa_etapa_duplicada() -> None:
    e = EtapaFunil("enviado", Numero(Decimal("1000"), "medido"))
    with pytest.raises(ValueError):
        Braco("tratamento", (e, e))


def test_braco_e_imutavel_reatribuicao_do_histograma_levanta() -> None:
    braco = Braco("tratamento", ())
    with pytest.raises(AttributeError):
        braco.latencia_entrega_clique = ()  # type: ignore[misc]


def test_braco_e_imutavel_histograma_e_tupla_nao_aceita_escrita_em_lugar() -> None:
    """A troca de Mapping[str,int] (dict, mutavel em lugar mesmo dentro de
    um frozen dataclass) por tuple[tuple[BucketLatencia, Numero], ...] e
    o que faz Braco ser imutavel de verdade -- nao so a reatribuicao do
    atributo, o proprio container tambem recusa escrita."""
    braco = Braco("tratamento", ())
    with pytest.raises(TypeError):
        braco.latencia_entrega_clique[0] = (  # type: ignore[index]
            "<=0s", Numero(Decimal("99"), "medido"),
        )


def test_braco_recusa_latencia_com_baldes_fora_de_ordem_ou_incompletos() -> None:
    e = EtapaFunil("enviado", Numero(Decimal("1000"), "medido"))
    baldes_fora_de_ordem = tuple(reversed(Braco("tratamento", (e,)).latencia_entrega_clique))
    with pytest.raises(ValueError):
        Braco("tratamento", (e,), baldes_fora_de_ordem)
