from pathlib import Path


def carrega(caminho: Path, *, cabecalho: str = "tools:") -> tuple[dict[str, str], ...]:
    itens: list[dict[str, str]] = []
    corrente: dict[str, str] | None = None

    for n, bruta in enumerate(caminho.read_text(encoding="utf-8").splitlines(), 1):
        if not bruta.strip():
            continue
        indent = len(bruta) - len(bruta.lstrip(" "))
        linha = bruta.strip()

        if indent == 0:
            if linha != cabecalho:
                raise ValueError(f"linha {n}: cabecalho inesperado {linha!r}")
            continue

        if indent == 2:
            if not linha.startswith("- "):
                raise ValueError(f"linha {n}: item deve comecar com '- '")
            if corrente is not None:
                itens.append(corrente)
            corrente = {}
            linha = linha[2:]
        elif indent == 4:
            if corrente is None:
                raise ValueError(f"linha {n}: campo sem item aberto")
        else:
            raise ValueError(f"linha {n}: indentacao {indent} nao permitida")

        chave, sep, valor = linha.partition(":")
        if not sep:
            raise ValueError(f"linha {n}: falta ':'")
        corrente[chave.strip()] = valor.strip()

    if corrente is not None:
        itens.append(corrente)
    return tuple(itens)
