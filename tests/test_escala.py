import time
from pathlib import Path

import pytest

from harness.ingest.pii_guard import PIIEncontrada
from harness.ingest.reader import le_csv

CAB = "event_time,user_ext_id,obs\n"
LIMPA = "Mon Jul 28 2026 11:34:33 GMT+0,1234567890,ok\n"
SUJA = "Mon Jul 28 2026 11:34:33 GMT+0,1234567890,ana@brand-b.example\n"
TETO_S = 5.0


def test_50k_linhas_dentro_do_teto(tmp_path: Path) -> None:
    p = tmp_path / "grande.csv"
    p.write_text(CAB + LIMPA * 50_000, encoding="utf-8", newline="\n")
    t = time.perf_counter()
    assert sum(1 for _ in le_csv(p)) == 50_000
    assert time.perf_counter() - t < TETO_S


def test_pii_na_linha_40000_recusa_o_arquivo(tmp_path: Path) -> None:
    p = tmp_path / "sujo.csv"
    p.write_text(
        CAB + LIMPA * 39_999 + SUJA + LIMPA * 10_000, encoding="utf-8", newline="\n"
    )
    with pytest.raises(PIIEncontrada) as exc:
        list(le_csv(p))
    assert exc.value.achados[0].linha == 40_000
    assert "ana@brand-b.example" not in str(exc.value)
