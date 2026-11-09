import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from harness.contracts import Braco, Digest, EtapaFunil, Numero
from harness.persist.resultados import grava_resultado, le_digest, lista_resultados

INI, FIM = "2026-07-01T00:00:00Z", "2026-07-08T00:00:00Z"


def _digest(casa: str = "brand_a", campanha_id: str = "9000001") -> Digest:
    e = EtapaFunil("enviado", Numero(Decimal("100"), "medido"))
    return Digest(
        casa=casa, fase="leitura", universo="csv", campanha_id=campanha_id,
        janela_inicio=INI, janela_fim=FIM, hipotese="h", contexto="",
        bracos=(Braco("tratamento", (e,)),),
        proveniencia={"fonte": "csv", "caminho": "x.csv", "sha256": "a" * 64},
    )


def test_grava_resultado_no_caminho_esperado(tmp_path: Path) -> None:
    d = _digest()
    agora = datetime(2026, 8, 1, 12, 0, 0, 123456, tzinfo=UTC)
    caminho = grava_resultado(d, saida=tmp_path, agora=agora)
    assert caminho == tmp_path / "brand_a" / "9000001" / "20260801T120000.123456Z.json"
    assert caminho.exists()


def test_grava_resultado_conteudo_tem_digest_hash_e_lints(tmp_path: Path) -> None:
    d = _digest()
    caminho = grava_resultado(d, saida=tmp_path, agora=datetime(2026, 8, 1, tzinfo=UTC))
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados["gravado_em"] == "2026-08-01T00:00:00.000000Z"
    assert dados["lints"] == {}
    assert dados["digest"]["campanha_id"] == "9000001"
    assert isinstance(dados["digest_hash"], str) and len(dados["digest_hash"]) == 64


def test_grava_resultado_nunca_sobrescreve(tmp_path: Path) -> None:
    d = _digest()
    agora = datetime(2026, 8, 1, tzinfo=UTC)
    grava_resultado(d, saida=tmp_path, agora=agora)
    with pytest.raises(FileExistsError):
        grava_resultado(d, saida=tmp_path, agora=agora)


def test_le_digest_reconstroi_o_que_grava_resultado_escreveu(tmp_path: Path) -> None:
    original = _digest()
    caminho = grava_resultado(original, saida=tmp_path, agora=datetime(2026, 8, 1, tzinfo=UTC))
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    reconstruido = le_digest(dados["digest"])
    assert reconstruido == original


def test_le_digest_recusa_proveniencia_sem_fonte() -> None:
    dados = {
        "casa": "brand_a", "fase": "leitura", "universo": "csv", "campanha_id": "x",
        "janela_inicio": INI, "janela_fim": FIM, "hipotese": "h", "contexto": "",
        "bracos": [{"nome": "tratamento", "etapas": []}],
        "proveniencia": {},
    }
    with pytest.raises(ValueError, match="proveniencia"):
        le_digest(dados)


def test_lista_resultados_ordena_por_tempo(tmp_path: Path) -> None:
    d = _digest()
    c1 = grava_resultado(d, saida=tmp_path, agora=datetime(2026, 8, 1, 10, tzinfo=UTC))
    c2 = grava_resultado(d, saida=tmp_path, agora=datetime(2026, 8, 1, 12, tzinfo=UTC))
    assert lista_resultados(tmp_path) == (c1, c2)


def test_lista_resultados_filtra_por_desde(tmp_path: Path) -> None:
    d = _digest()
    grava_resultado(d, saida=tmp_path, agora=datetime(2026, 8, 1, 10, tzinfo=UTC))
    c2 = grava_resultado(d, saida=tmp_path, agora=datetime(2026, 8, 1, 12, tzinfo=UTC))
    achados = lista_resultados(tmp_path, desde="2026-08-01T11:00:00.000000Z")
    assert achados == (c2,)
