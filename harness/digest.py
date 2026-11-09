import hashlib
import json
from decimal import Decimal
from typing import Any


def _serializa(obj: Any) -> str:
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"tipo nao serializavel: {type(obj)}")


def canonico(dados: dict[str, Any]) -> bytes:
    texto = json.dumps(
        dados,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_serializa,
    )
    return texto.encode("utf-8")


def digest_hash(dados: dict[str, Any]) -> str:
    return hashlib.sha256(canonico(dados)).hexdigest()
