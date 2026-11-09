# CRM Campaign Harness

A deterministic harness that only issues a verdict on a CRM campaign (SMS / e-mail / on-site
journeys) when the measurement method holds. It turns raw campaign exports into a hashed,
PII-free digest. Quality gates run over that digest. Every number in a published verdict can be
traced to its source, the gate thresholds that applied and the code commit.

> Built while contracted by an iGaming operator; brand names, data and figures removed.
> Built with Claude Code as a pair programmer.

The method notes (`CRM.md`, `references/`) are in Portuguese, the language the project was run in.
Code identifiers are mostly Portuguese too (`casa` = operator/brand, `braco` = test arm,
`piso` = threshold, `achado` = finding, `veredito` = verdict).

## Why

Campaign reports often present a comparative number as a causal result. Examples: a "control
group" that also received a message, a funnel stage measured differently in each arm, a
hypothesis written after the numbers were read. This harness makes those failures explicit and
blocks the verdict when they happen.

## Architecture

```
Z0 (raw, outside the repo)      Z1 (digest, hashed)              Z2 (ledger / publish)
CSV export / Postgres replica → harness ingest → Digest ──lint──→ resultados/<casa>/<campaign>/<ts>.json
        │  pii_guard (CPF/e-mail refused)        │  C2, C3, C6, C7, detectors        │
        │  aggregates only, no per-user rows      │  thresholds with lineage          ▼
        │                                         │                          harness publica
SpecCampanha (plan) → harness preflight (C8 MDE, C9, C11) ───────────────→ guard → POST to consumer
Risk-squad summary JSON → harness risco (exact-key schema, coverage floor) ───────┘
Named SQL catalog → harness query (report only, never published)
```

| Module | Role |
|---|---|
| `harness/ingest/` | `FonteZ0` protocol (CSV, Postgres adapters), aggregation into a `Digest`, PII guard, communication-fact vocabulary, 7-query parameterised SQL catalog |
| `harness/contracts.py` | Frozen dataclasses: `Digest`, `Braco` (holdout / comparison / treatment), `EtapaFunil`, `Numero` (value + label `medido`/`estimado`/`ausente`) |
| `harness/lint/` | Gates: C3 delivery floor, C2 arm comparability, temporal-order check, CTOR/opt-out anomaly detectors (detect + attach evidence, never drop rows) |
| `harness/preflight.py` | Pre-launch audit: C8 minimum detectable effect vs. baseline (`statistics.NormalDist`, α=0.05, power=0.80), C9 control conversion source, C11 duration vs. delays |
| `harness/pisos.py` | Thresholds with lineage: `default_nao_validado` / `crm_md` / `cli` |
| `harness/risco/` | Ingests aggregated verdicts produced by separate risk-analysis squads; validates exact keys, coverage floor, selection-bias findings |
| `harness/publica/` | Pure document builder (versions 1–3), PII guard over every reachable string, isolated `urllib` sender with a 4 MB cap |
| `harness/persist/` | Append-only result files, never overwritten |
| `tools/gera_golden.py` | Deterministic generator of the synthetic golden fixtures |

The consumer interface the publisher implements is described in
[`references/consumer-interface.md`](references/consumer-interface.md).

## Stack

- Python ≥ 3.11, **standard library only** at runtime (`dependencies = []`).
- Optional: `psycopg[binary]` (extra `postgres`) for the read-only replica adapter.
- Dev: `pytest`, `ruff`, `mypy --strict` (config in `pyproject.toml`).
- AI: none at runtime. The harness is deterministic by design. A model may *choose* a named
  query, but it never writes SQL (E3 in `CRM.md`).

## Contracts and invariants

- **No real IDs past Z0.** A digest holds funnel aggregates only, with no per-user rows. `CRM.md` §5 specifies a keyed `id_anon` (HMAC-SHA256, salt from env) for any future per-user artefact. That is a design rule and is not implemented in code yet.
- **The hypothesis comes before the numbers.** Declared context and hypothesis are immutable, hashed fields of the digest (C7).
- **Holdout ≠ comparison.** `BracoNome` is `holdout | comparacao | tratamento`. Without a real holdout, the verdict is comparative, never causal.
- **Provenance is mandatory.** Every digest carries `proveniencia` (source, path or query, sha256).
- **Unknown is never zero.** Missing measurements are labelled `ausente` and suspend the verdict. They are never treated as passing.
- **Exact schemas.** Risk-squad JSON and query params must match the declared key set exactly, with no subsets and no extras.
- **The guard runs before every send.** Any CPF or e-mail pattern anywhere in the outgoing document refuses the whole document.
- **Determinism.** The same inputs give byte-identical digests and hashes across processes and `PYTHONHASHSEED` values (tested).

## Tests

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e . pytest
git init -q 2>/dev/null; git add -A; git commit -qm init 2>/dev/null  # `publica` stamps the git commit
python -m pytest -q
```

Current result on this sanitized copy: **315 tests: 313 passed, 2 xfailed (documented expected failures)**.
Golden fixtures in `tests/golden/` are synthetic. `tools/gera_golden.py` regenerates them byte for byte
(`tests/test_gera_golden.py`). Campaign `demo_9000001` and users `u_NNNN` are made up.

## Run (placeholders)

```bash
# operators ("casas") allowed: config/casas.yaml (brand_a, brand_b by default)
harness ingest /path/outside/repo/export.csv --casa brand_a --campanha <id> --braco tratamento \
  --de 2026-01-01T00:00:00Z --ate 2026-01-08T00:00:00Z --universo csv \
  --hipotese "<written before reading any number>"
harness lint
harness preflight --casa brand_a --universo csv --regua <name> --base-estimada <n> \
  --pct-holdout 0.05 --conversao-esperada <rate> --fonte-conversao-controle no_flow \
  --max-duration-s <s> --delays-s 60,3600 --piso-mde-ok <rate>
harness publica --dry-run                      # build + guard, no network

# optional
export HARNESS_PG_DSN_BRAND_A='<postgres DSN, read-only user>'
harness query executive_kpis --casa brand_a --param janela_inicio=<date> --param janela_fim=<date>
export CONSUMER_URL='<https endpoint>' CONSUMER_HARNESS_KEY='<key>'
harness publica
```

## Security

- Secrets come from environment variables only (`HARNESS_PG_DSN_<CASA>`,
  `CONSUMER_URL`, `CONSUMER_HARNESS_KEY`). None of them has a fallback, so a missing variable fails loudly.
- `.gitignore` is an allowlist. Only code, docs, config and the synthetic test fixtures can be committed. A pre-commit hook (`.githooks/pre-commit`) blocks forbidden files.
- No real data is included. Operator names, table names, campaign IDs, credentials and business
  figures were removed or replaced with generic placeholders (`brand_a`, `public.casino_activity`, …).
- The Postgres adapter runs queries in a read-only transaction with driver-bound parameters, never string interpolation.

## License

All rights reserved unless a license file is added.
