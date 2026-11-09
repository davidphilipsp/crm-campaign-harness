"""Prova por execucao (nao por leitura de codigo) que 'harness ingest' e
'harness lint' -- sobre o MESMO digest -- produzem a mesma lista de
achados, gates e detectores. So e possivel porque histograma de latencia
entrega->clique e contador de optout passaram a viver no Digest (Z1) em
vez de so existirem em linha bruta (Z0, TTL 30 dias): antes deste commit,
detecta_ctor_anomalo/detecta_optout_alto liam `linhas` e um digest relido
do disco nunca tinha para onde essas funcoes olharem.
"""

import json
import sys
from pathlib import Path

import pytest

from harness.cli import main
from harness.lint.runner import roda_lint
from harness.persist.resultados import le_achados, le_digest, lista_resultados
from harness.pisos import carrega_piso

CAMINHO_GOLDEN_CSV = Path("tests/golden/demo_9000001/entrada.csv")


def test_roda_ingest_e_roda_lint_sobre_o_mesmo_digest_dao_a_mesma_lista_de_achados(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    saida = tmp_path / "resultados"
    argv = [
        "harness", "ingest", str(CAMINHO_GOLDEN_CSV),
        "--casa", "brand_a", "--campanha", "9000001", "--braco", "tratamento",
        "--de", "2026-07-01T00:00:00Z", "--ate", "2026-07-28T00:00:00Z",
        "--universo", "csv", "--hipotese", "oferta converte mais que a generica",
        "--saida", str(saida),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    main()  # roda_ingest de ponta a ponta -- digest fresco, roda_lint com dado recem-lido

    (caminho,) = lista_resultados(saida)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    achados_ingest = le_achados(dados["achados"])

    # 'harness lint': releitura do mesmo resultado persistido, sem nenhum
    # acesso a linha bruta -- so o que sobreviveu no Digest.
    digest_relido = le_digest(dados["digest"])
    pisos = {
        "C3_ENTREGA_MINIMA": carrega_piso("C3_ENTREGA_MINIMA"),
        "C2_DESVIO_MAX_BRACOS": carrega_piso("C2_DESVIO_MAX_BRACOS"),
        "CTOR_MAX_ANOMALO": carrega_piso("CTOR_MAX_ANOMALO"),
    }
    achados_lint = roda_lint(digest_relido, pisos=pisos).achados

    assert achados_ingest == achados_lint
    assert achados_ingest, "fixture precisa disparar pelo menos um achado -- senao a prova e vazia"

    origens = {a.origem for a in achados_ingest}
    assert "C3" in origens, "achado de GATE tem que estar presente e bater nos dois caminhos"
    assert "ctor_anomalo" in origens, "achado de DETECTOR tem que estar presente e bater tambem"
