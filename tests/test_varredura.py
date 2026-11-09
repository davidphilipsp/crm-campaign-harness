import pytest

from harness.ingest.pii_guard import AchadoPII, PIIEncontrada, varre_linha


def test_linha_limpa_nao_produz_achado() -> None:
    assert varre_linha(1, {"user_ext_id": "1234567890", "fact_type_id": "3"}) == ()


def test_detecta_email_em_coluna_livre() -> None:
    (a,) = varre_linha(40000, {"obs": "contato ana@brand-b.example"})
    assert a == AchadoPII(linha=40000, coluna="obs", tipo="email")


def test_detecta_cpf() -> None:
    (a,) = varre_linha(7, {"doc": "111.444.777-35"})
    assert a.tipo == "cpf"


def test_achado_nao_carrega_valor() -> None:
    campos = {f.name for f in AchadoPII.__dataclass_fields__.values()}
    assert "valor" not in campos


def test_excecao_nao_expoe_valor() -> None:
    with pytest.raises(PIIEncontrada) as exc:
        raise PIIEncontrada(varre_linha(40000, {"obs": "ana@brand-b.example"}))
    assert "ana@brand-b.example" not in str(exc.value)


def test_id_tecnico_de_11_digitos_nao_e_cpf() -> None:
    # 11144477735 tem DV valido, mas em coluna de ID nao e CPF
    assert varre_linha(1, {"engagement_id": "11144477735"}) == ()


def test_mesmo_valor_em_coluna_livre_e_cpf() -> None:
    (a,) = varre_linha(1, {"observacao": "11144477735"})
    assert a.tipo == "cpf"


def test_coluna_desconhecida_continua_suspeita() -> None:
    (a,) = varre_linha(1, {"campo_novo": "11144477735"})
    assert a.tipo == "cpf"
