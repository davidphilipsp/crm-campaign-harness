import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent / "fixtures" / "hash_estavel.py"


def _roda(seed: str) -> str:
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        check=True,
        env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": seed},
    )
    return r.stdout.strip()


def test_hash_estavel_entre_processos() -> None:
    saidas = {_roda(s) for s in ("0", "1", "99999")}
    assert len(saidas) == 1, f"hash instavel: {saidas}"
