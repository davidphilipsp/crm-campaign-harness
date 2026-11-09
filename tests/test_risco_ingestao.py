"""'harness risco' (E23): ingestao do resumo que um risk squad entrega ao
final da propria analise. So valida forma e piso de cobertura -- nunca
chama MCP, nunca roda SQL, nunca aceita player_id."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from harness.risco.ingestao import ChavesDivergentes, ingere


def _payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "casa": "brand_a",
        "squad": "brand-a-risk-squad",
        "acao": "antichurn-bigbass-low",
        "janela_inicio": "2026-08-06T00:27:00Z",
        "janela_fim": "2026-08-07T01:34:03Z",
        "segmentos": [
            {
                "nome": "low",
                "custo_total": "6823.72",
                "unidades_ofertadas": 8039,
                "unidades_usadas": 6328,
                "taxa_aproveitamento": "0.787",
                "turnover_atribuido": None,
            }
        ],
        "cobertura_pct": {"valor": "0.795", "rotulo": "medido"},
        "vies_selecao": {
            "tipo": "vies_selecao",
            "resumo": "exposto ja era mais ativo que o controle antes da campanha",
            "evidencia": {"turnover_exposto_pre": "1200.00", "turnover_controle_pre": "450.00"},
        },
        "achados_governanca": [
            {
                "tipo": "linha_nao_paga",
                "resumo": "Missao Artemis nunca foi paga",
                "evidencia": {"torneio": "Missao Artemis", "valor_nominal": "25000.00"},
            }
        ],
    }
    base.update(overrides)
    return base


def _grava(tmp_path: Path, payload: dict[str, object], *, nome: str = "veredicto.json") -> Path:
    caminho = tmp_path / nome
    caminho.write_text(json.dumps(payload), encoding="utf-8")
    return caminho


def test_ingere_caminho_feliz(tmp_path: Path) -> None:
    caminho = _grava(tmp_path, _payload())
    v = ingere(caminho)

    assert v.fase == "risco"
    assert v.casa == "brand_a"
    assert v.squad == "brand-a-risk-squad"
    assert v.acao == "antichurn-bigbass-low"
    assert len(v.segmentos) == 1
    assert v.segmentos[0].custo_total == Decimal("6823.72")
    assert v.segmentos[0].turnover_atribuido is None
    assert v.vies_selecao is not None
    assert v.vies_selecao.origem == "vies_selecao"
    assert len(v.achados_governanca) == 1
    assert v.achados_governanca[0].origem == "linha_nao_paga"


def test_ingere_calcula_cobertura_ok_contra_o_piso(tmp_path: Path) -> None:
    # 0.795 < piso 0.90 -- suspenso, nao descartado. Piso decidido em
    # CRM.md §6 (E25) -- ingere() le a CRM.md real do repo (cwd), sem
    # jeito de injetar outra: mesmo padrao de roda_ingest/roda_preflight.
    caminho = _grava(tmp_path, _payload(cobertura_pct={"valor": "0.795", "rotulo": "medido"}))
    v = ingere(caminho)
    assert v.cobertura_ok is False
    assert v.cobertura_pct.valor == Decimal("0.795")
    assert v.cobertura_pct.rotulo == "medido"
    assert v.cobertura_piso.valor == Decimal("0.90")
    assert v.cobertura_piso.origem == "crm_md"


def test_ingere_cobertura_acima_do_piso_fica_ok(tmp_path: Path) -> None:
    caminho = _grava(tmp_path, _payload(cobertura_pct={"valor": "0.99", "rotulo": "medido"}))
    v = ingere(caminho)
    assert v.cobertura_ok is True


def test_ingere_cobertura_ausente_fica_suspensa_nao_recusada(tmp_path: Path) -> None:
    """E24: sessoes que produziram os relatorios de AntiChurn ja foram
    encerradas -- nenhum numero de cobertura existe pra elas. 'ausente' e
    uma medicao valida, nao um erro; o veredito so fica suspenso."""
    caminho = _grava(tmp_path, _payload(cobertura_pct={"valor": None, "rotulo": "ausente"}))
    v = ingere(caminho)
    assert v.cobertura_pct.valor is None
    assert v.cobertura_pct.rotulo == "ausente"
    assert v.cobertura_ok is False


def test_ingere_recusa_cobertura_ausente_com_valor_presente(tmp_path: Path) -> None:
    caminho = _grava(
        tmp_path, _payload(cobertura_pct={"valor": "0.5", "rotulo": "ausente"})
    )
    with pytest.raises(ValueError, match="ausente"):
        ingere(caminho)


def test_ingere_recusa_cobertura_com_chave_extra(tmp_path: Path) -> None:
    caminho = _grava(
        tmp_path,
        _payload(cobertura_pct={"valor": "0.9", "rotulo": "medido", "fonte": "extra"}),
    )
    with pytest.raises(ChavesDivergentes, match="cobertura_pct"):
        ingere(caminho)


def test_ingere_aceita_vies_selecao_ausente(tmp_path: Path) -> None:
    caminho = _grava(tmp_path, _payload(vies_selecao=None))
    v = ingere(caminho)
    assert v.vies_selecao is None


def test_ingere_proveniencia_carrega_squad_caminho_e_hash(tmp_path: Path) -> None:
    caminho = _grava(tmp_path, _payload())
    v = ingere(caminho)
    assert v.proveniencia["fonte"] == "squad"
    assert v.proveniencia["squad"] == "brand-a-risk-squad"
    assert v.proveniencia["caminho"] == str(caminho)
    assert len(v.proveniencia["sha256"]) == 64


def test_ingere_recusa_chave_topo_faltando(tmp_path: Path) -> None:
    payload = _payload()
    del payload["cobertura_pct"]
    caminho = _grava(tmp_path, payload)
    with pytest.raises(ChavesDivergentes, match=r"faltando=\['cobertura_pct'\]"):
        ingere(caminho)


def test_ingere_recusa_chave_topo_sobrando(tmp_path: Path) -> None:
    caminho = _grava(tmp_path, _payload(extra="nao deveria estar aqui"))
    with pytest.raises(ChavesDivergentes, match=r"sobrando=\['extra'\]"):
        ingere(caminho)


def test_ingere_recusa_segmento_com_chave_faltando(tmp_path: Path) -> None:
    payload = _payload()
    segmentos = payload["segmentos"]
    assert isinstance(segmentos, list)
    del segmentos[0]["taxa_aproveitamento"]
    caminho = _grava(tmp_path, payload)
    with pytest.raises(ChavesDivergentes, match=r"segmentos\[0\]"):
        ingere(caminho)


def test_ingere_recusa_achado_governanca_com_chave_extra(tmp_path: Path) -> None:
    payload = _payload()
    achados = payload["achados_governanca"]
    assert isinstance(achados, list)
    achados[0]["player_id"] = "12345"
    caminho = _grava(tmp_path, payload)
    with pytest.raises(ChavesDivergentes, match=r"achados_governanca\[0\]"):
        ingere(caminho)


def test_ingere_recusa_casa_desconhecida(tmp_path: Path) -> None:
    caminho = _grava(tmp_path, _payload(casa="cassino_inexistente"))
    with pytest.raises(ValueError, match="casa desconhecida"):
        ingere(caminho)


def test_ingere_recusa_squad_desconhecido(tmp_path: Path) -> None:
    caminho = _grava(tmp_path, _payload(squad="squad_que_nao_existe"))
    with pytest.raises(ValueError, match="squad desconhecido"):
        ingere(caminho)
