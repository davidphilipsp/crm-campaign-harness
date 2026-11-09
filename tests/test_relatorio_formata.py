from harness.relatorio.formata import formata_csv, formata_json


def test_formata_csv_usa_colunas_da_primeira_linha() -> None:
    linhas = [{"player_id": "1", "ggr": "10"}, {"player_id": "2", "ggr": "20"}]
    saida = formata_csv(linhas)
    cabecalho, l1, l2 = saida.splitlines()
    assert cabecalho == "player_id,ggr"
    assert l1 == "1,10"
    assert l2 == "2,20"


def test_formata_csv_sem_linhas_devolve_vazio() -> None:
    assert formata_csv([]) == ""


def test_formata_json_carrega_proveniencia_no_envelope() -> None:
    import json

    linhas = [{"player_id": "1", "ggr": "10"}]
    proveniencia = {"fonte": "postgres", "casa": "brand_a", "query": "executive_kpis", "sha256": "a"}
    saida = json.loads(formata_json(linhas, proveniencia))
    assert saida["proveniencia"] == proveniencia
    assert saida["linhas"] == linhas
