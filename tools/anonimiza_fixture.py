#!/usr/bin/env python3
"""Ferramenta de quebra-vidro: troca user_ext_id por u_NNNN sequencial num
CSV que ja existe. So faz sentido se algum dia for preciso capturar um
export real de novo pra virar fixture -- nenhum teste do repo chama esta
funcao hoje, e nenhuma fixture de teste depende dela: as fixtures golden
(tests/golden/) sao geradas do zero por tools/gera_golden.py, sinteticas
desde a origem, sem dado real pra anonimizar.
"""

import csv
import os
import sys


def anonimiza(caminho: str) -> None:
    with open(caminho, newline="", encoding="utf-8") as f:
        leitor = csv.reader(f)
        cabecalho = next(leitor)
        idx = cabecalho.index("user_ext_id")

        tmp = caminho + ".tmp"
        with open(tmp, "w", newline="\n", encoding="utf-8") as out:
            escritor = csv.writer(out, lineterminator="\n")
            escritor.writerow(cabecalho)

            mapa: dict[str, str] = {}
            proximo = 1
            for linha in leitor:
                original = linha[idx]
                novo_id = mapa.get(original)
                if novo_id is None:
                    novo_id = f"u_{proximo:04d}"
                    mapa[original] = novo_id
                    proximo += 1
                linha[idx] = novo_id
                escritor.writerow(linha)

    os.replace(tmp, caminho)


def main() -> None:
    if len(sys.argv) != 2:
        print("uso: anonimiza_fixture.py <caminho.csv>", file=sys.stderr)
        raise SystemExit(1)
    anonimiza(sys.argv[1])


if __name__ == "__main__":
    main()
