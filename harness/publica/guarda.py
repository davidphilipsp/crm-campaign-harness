"""P2: lint de saida. O pii_guard protege a INGESTAO; ninguem protegia a
PUBLICACAO -- o documento sai da VM interna para um app com JWT de time,
a unica travessia do sistema que sai da fronteira de confianca.

Varre TODA string alcancavel no documento montado, em qualquer
profundidade, sob qualquer chave -- so escapa da varredura quem estiver
em CAMPOS_NAO_VARRIDOS (allowlist, nao denylist: campo novo nasce
varrido por padrao). Achou -> recusa o documento inteiro (nao mascara,
nao trunca, nao envia). Reusa harness.ingest.pii_guard.varre_linha -- o
detector ja existe e ja sabe nao vazar valor na mensagem de erro.

COLUNAS_ID_TECNICO do pii_guard nao se aplica aqui de proposito: esses
campos sao prosa do operador, nunca coluna tecnica do Smartico. Um numero
de 11 digitos dentro de `contexto` e suspeito de verdade e deve disparar.
"""

from collections.abc import Iterator

from harness.ingest.pii_guard import AchadoPII, PIIEncontrada, varre_linha

# Allowlist do que NAO e varrido. Denylist falha aberta -- campo novo nasce
# desprotegido; allowlist falha fechado -- campo novo nasce varrido por
# padrao. Cada entrada abaixo precisa provar, contra o golden ou contra uma
# fixture real, que precisa ficar de fora. Comeca vazia de proposito.
CAMPOS_NAO_VARRIDOS: frozenset[str] = frozenset()


def _valores_de_risco(no: object, caminho: str = "") -> Iterator[tuple[str, str]]:
    """Toda string alcancavel no documento, em qualquer profundidade, sob
    qualquer chave -- exceto o que estiver em CAMPOS_NAO_VARRIDOS."""
    if isinstance(no, dict):
        for chave, valor in no.items():
            if chave in CAMPOS_NAO_VARRIDOS:
                continue
            novo_caminho = f"{caminho}.{chave}" if caminho else str(chave)
            yield from _valores_de_risco(valor, novo_caminho)
    elif isinstance(no, list):
        for i, item in enumerate(no):
            yield from _valores_de_risco(item, f"{caminho}[{i}]")
    elif isinstance(no, str):
        yield caminho, no


def varre_documento(documento: dict[str, object]) -> None:
    """Levanta PIIEncontrada se achar CPF ou e-mail em campo de texto livre."""
    achados: list[AchadoPII] = []
    for n, (caminho, valor) in enumerate(_valores_de_risco(documento), 1):
        achados.extend(varre_linha(n, {caminho: valor}))
    if achados:
        raise PIIEncontrada(tuple(achados))
