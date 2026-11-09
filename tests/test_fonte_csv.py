from pathlib import Path

import pytest

from harness.ingest.fonte import FonteZ0
from harness.ingest.fonte_csv import FonteCSV
from harness.ingest.pii_guard import PIIEncontrada

CAB = "event_time,user_ext_id,obs\n"


def test_fonte_csv_satisfaz_o_protocolo(tmp_path: Path) -> None:
    p = tmp_path / "entrada.csv"
    p.write_text(CAB + "t,u_0001,x\n", encoding="utf-8")
    assert isinstance(FonteCSV(p), FonteZ0)


def test_fonte_csv_le_linhas_e_devolve_proveniencia(tmp_path: Path) -> None:
    p = tmp_path / "entrada.csv"
    p.write_text(CAB + "t,u_0001,x\n", encoding="utf-8")
    fonte = FonteCSV(p)
    assert list(fonte.linhas()) == [{"event_time": "t", "user_ext_id": "u_0001", "obs": "x"}]
    prov = fonte.proveniencia()
    assert prov["fonte"] == "csv"
    assert prov["caminho"] == str(p)
    assert len(prov["sha256"]) == 64


def test_fonte_csv_recusa_linha_com_pii(tmp_path: Path) -> None:
    p = tmp_path / "entrada.csv"
    p.write_text(CAB + "t,u_0001,fulano@example.com\n", encoding="utf-8")
    with pytest.raises(PIIEncontrada):
        list(FonteCSV(p).linhas())
