"""Formata o resultado de uma query do catalogo (E8, CRM.md) para saida
tabular (CSV) ou estruturada (JSON) -- pura, sem I/O, simetrica a
harness/publica/documento.py: o nucleo formata, a borda (cli.py) decide
onde escrever.

`harness query` nunca alimenta `resultados/` nem `harness publica` (E22,
CRM.md): estas linhas carregam `player_id` cru da replica PAM, sem
`id_anon` (Sec. 5, CRM.md) -- atravessar a fronteira de confianca em
direcao ao consumidor downstream exigiria a mesma anonimizacao que o resto do harness
aplica, e isto nao existe aqui de proposito. Fica em disco ou stdout, na
maquina interna, para o squad que ja consumia esse dado direto do
Postgres.
"""

import csv
import io
import json
from collections.abc import Mapping, Sequence


def formata_csv(linhas: Sequence[Mapping[str, str]]) -> str:
    """Colunas vem da primeira linha -- todo resultado de SQL agregado tem
    o mesmo shape em todas as linhas. Sem linhas, sem cabecalho: nada para
    nomear."""
    if not linhas:
        return ""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=tuple(linhas[0].keys()))
    writer.writeheader()
    writer.writerows(linhas)
    return buffer.getvalue()


def formata_json(linhas: Sequence[Mapping[str, str]], proveniencia: Mapping[str, str]) -> str:
    """Proveniencia sempre no envelope (E7, CRM.md) -- quem le o JSON sabe
    qual query, qual casa, qual hash gerou estas linhas, mesmo fora do
    harness."""
    return json.dumps(
        {"proveniencia": dict(proveniencia), "linhas": list(linhas)},
        sort_keys=True,
        ensure_ascii=False,
        indent=2,
    )
