from pathlib import Path

import pytest

from harness.ingest.catalogo import DIRETORIO_PADRAO, carrega, carrega_por_nome

NOMES_ESPERADOS = (
    "executive_kpis",
    "provider_performance",
    "player_risk_signals",
    "affiliate_performance",
    "game_performance",
    "payment_field_profile",
    "client_field_profile",
)


@pytest.mark.parametrize("nome", NOMES_ESPERADOS)
def test_cada_query_do_catalogo_carrega_e_bate_params(nome: str) -> None:
    q = carrega_por_nome(nome)
    assert q.nome == nome
    assert q.sql
    assert len(q.sha256) == 64
    assert q.params  # todas exigem pelo menos um param declarado


def test_sha256_e_estavel_entre_cargas() -> None:
    a = carrega_por_nome("executive_kpis")
    b = carrega_por_nome("executive_kpis")
    assert a.sha256 == b.sha256
    assert a == b


def test_diretorio_padrao_so_tem_os_nomes_esperados() -> None:
    achados = {p.stem for p in DIRETORIO_PADRAO.glob("*.sql")}
    assert achados == set(NOMES_ESPERADOS)


def test_recusa_nome_desconhecido() -> None:
    with pytest.raises(ValueError, match="desconhecida"):
        carrega_por_nome("query_que_nao_existe")


def test_recusa_param_usado_no_sql_mas_nao_declarado(tmp_path: Path) -> None:
    p = tmp_path / "ruim.sql"
    p.write_text(
        "-- nome: ruim\n-- params: janela_inicio\n-- devolve: agregado\n"
        "select * from t where dia = %(janela_fim)s\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="nao batem"):
        carrega(p)


def test_recusa_param_declarado_mas_nao_usado_no_sql(tmp_path: Path) -> None:
    p = tmp_path / "ruim.sql"
    p.write_text(
        "-- nome: ruim\n-- params: janela_inicio, janela_fim\n-- devolve: agregado\n"
        "select * from t where dia = %(janela_inicio)s\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="nao batem"):
        carrega(p)


def test_recusa_campo_obrigatorio_ausente(tmp_path: Path) -> None:
    p = tmp_path / "ruim.sql"
    p.write_text("-- nome: ruim\n-- params:\nselect 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="obrigatorio"):
        carrega(p)


def test_recusa_nome_declarado_diferente_do_arquivo(tmp_path: Path) -> None:
    p = tmp_path / "arquivo.sql"
    p.write_text(
        "-- nome: outro_nome\n-- params:\n-- devolve: agregado\nselect 1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="nao bate"):
        carrega(p)


def test_recusa_linha_de_cabecalho_mal_formada(tmp_path: Path) -> None:
    p = tmp_path / "ruim.sql"
    p.write_text("-- isto nao e chave valor\nselect 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mal formada"):
        carrega(p)


def test_recusa_corpo_vazio(tmp_path: Path) -> None:
    p = tmp_path / "ruim.sql"
    p.write_text("-- nome: ruim\n-- params:\n-- devolve: agregado\n\n", encoding="utf-8")
    with pytest.raises(ValueError, match="corpo de query vazio"):
        carrega(p)


def test_recusa_arquivo_so_com_cabecalho(tmp_path: Path) -> None:
    p = tmp_path / "ruim.sql"
    p.write_text("-- nome: ruim\n-- params:\n-- devolve: agregado", encoding="utf-8")
    with pytest.raises(ValueError, match="so tem cabecalho"):
        carrega(p)
