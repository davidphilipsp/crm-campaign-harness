from pathlib import Path

import pytest

from harness.ingest.pii_guard import PIIEncontrada
from harness.ingest.reader import iso_utc, le_csv

CAB = "event_time,user_ext_id,obs\n"
LINHA = "Mon Jul 28 2026 11:34:33 GMT+0,1234567890,ok\n"


def _csv(tmp_path: Path, corpo: str) -> Path:
    p = tmp_path / "e.csv"
    p.write_text("\ufeff" + CAB + corpo, encoding="utf-8", newline="\n")
    return p


def test_le_linhas_limpas(tmp_path: Path) -> None:
    assert len(list(le_csv(_csv(tmp_path, LINHA * 3)))) == 3


def test_bom_nao_contamina_cabecalho(tmp_path: Path) -> None:
    (primeira,) = list(le_csv(_csv(tmp_path, LINHA)))
    assert "event_time" in primeira


def test_recusa_arquivo_inteiro_por_pii_tardia(tmp_path: Path) -> None:
    corpo = LINHA * 999 + "Mon Jul 28 2026 11:34:33 GMT+0,1234567890,ana@brand-b.example\n"
    with pytest.raises(PIIEncontrada) as exc:
        list(le_csv(_csv(tmp_path, corpo)))
    assert exc.value.achados[0].linha == 1000


def test_iso_utc_converte_formato_smartico() -> None:
    assert iso_utc("Mon Jul 28 2026 11:34:33 GMT+0") == "2026-07-28T11:34:33Z"


def test_iso_utc_recusa_formato_desconhecido() -> None:
    with pytest.raises(ValueError):
        iso_utc("28/07/2026 11:34")


def test_recusa_delimitador_errado(tmp_path: Path) -> None:
    p = tmp_path / "pv.csv"
    p.write_text(
        "\ufeffUser_Id;Last_Dep_Date;Segmento\n123;2026-07-01;high\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(ValueError):
        list(le_csv(p))


def test_recusa_header_inesperado(tmp_path: Path) -> None:
    p = tmp_path / "outro.csv"
    p.write_text("a,b,c\n1,2,3\n", encoding="utf-8", newline="\n")
    with pytest.raises(ValueError):
        list(le_csv(p, colunas_esperadas=("event_time", "user_ext_id")))
