---
name: crm-harness
description: Emite veredito causal sobre campanha de CRM apenas com metodo integro.
---

# Harness CRM

## Ferramentas

<!-- TOOLS:INICIO -->
| tool | zona | resumo |
|---|---|---|
| `ingest` | Z0->Z1 | le CSV bruto e produz digest agregado |
| `lint` | Z1 | roda C1-C7 sobre um digest |
| `verify` | Z2 | verifica a hash chain do ledger |
| `query` | fora do funil (reporte) | roda query do catalogo (E8) contra Postgres; nunca alimenta publica |
| `risco` | fora do funil (contrato de squad) | ingere veredito de risk squad (E23) e grava para publica ler |
<!-- TOOLS:FIM -->
