import re
from dataclasses import dataclass
from typing import Literal

TipoPII = Literal["cpf", "email"]

# Colunas de identificador tecnico do Smartico. Um id de 11 digitos satisfaz
# os DV de CPF por acaso em ~1 de cada 100 casos -- em 292k linhas isso sao
# milhares de falsos positivos. Allowlist: coluna nova NAO entra aqui,
# continua suspeita por padrao (§3.3).
COLUNAS_ID_TECNICO = frozenset({
    "user_id",
    "user_ext_id",
    "root_audience_id",
    "activity_type_id",
    "activity_id",
    "engagement_id",
    "engagement_uid",
    "resource_id",
    "fact_type_id",
    "communication_id",
    "fail_reason_id",
})


@dataclass(frozen=True)
class AchadoPII:
    """Localizacao de uma PII. Nunca carrega o valor encontrado (§3.3)."""

    linha: int
    coluna: str
    tipo: TipoPII


class PIIEncontrada(Exception):
    """Recusa da ingestao inteira. A mensagem so cita posicao, nunca conteudo."""

    def __init__(self, achados: tuple[AchadoPII, ...]) -> None:
        self.achados = achados
        resumo = ", ".join(f"{a.tipo}@linha {a.linha} col {a.coluna!r}" for a in achados)
        super().__init__(f"ingestao recusada: {resumo}")


def varre_linha(n: int, linha: dict[str, str]) -> tuple[AchadoPII, ...]:
    """Roda todos os detectores em todas as colunas. Acumula, nao para no primeiro."""
    achados: list[AchadoPII] = []
    for coluna, valor in linha.items():
        if coluna not in COLUNAS_ID_TECNICO and cpf_valido(valor):
            achados.append(AchadoPII(linha=n, coluna=coluna, tipo="cpf"))
        if tem_email(valor):
            achados.append(AchadoPII(linha=n, coluna=coluna, tipo="email"))
    return tuple(achados)


_EMAIL = re.compile(r"[^\s@]+@[^\s@.]+\.[A-Za-z]{2,}")


def tem_email(valor: str) -> bool:
    """True se o campo contem algo com forma de endereco de e-mail."""
    return bool(_EMAIL.search(valor))


def cpf_valido(valor: str) -> bool:
    """CPF com ou sem mascara. True somente se os dois DV conferem."""
    d = [int(c) for c in valor if c.isdigit()]

    if len(d) != 11:
        return False
    if len(set(d)) == 1:
        return False

    # DV1: 9 primeiros digitos, pesos 10,9,8,...,2
    soma1 = sum(a * b for a, b in zip(d[:9], range(10, 1, -1), strict=True))
    resto1 = soma1 % 11
    dv1 = 0 if resto1 < 2 else 11 - resto1
    if dv1 != d[9]:
        return False

    # DV2: 10 primeiros digitos, pesos 11,10,9,...,2
    soma2 = sum(a * b for a, b in zip(d[:10], range(11, 1, -1), strict=True))
    resto2 = soma2 % 11
    dv2 = 0 if resto2 < 2 else 11 - resto2
    return dv2 == d[10]
