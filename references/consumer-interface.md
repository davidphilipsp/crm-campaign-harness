# Interface do consumidor downstream

O harness publica um unico documento JSON para um servico consumidor externo
(um painel de decisao de CRM). O contrato original desse terceiro nao e
publicado aqui; este arquivo descreve apenas a interface que o codigo
implementa (`harness/publica/documento.py`, `harness/publica/envio.py`).

## Transporte

- `POST` JSON para `CONSUMER_URL`, cabecalho de autenticacao com `CONSUMER_HARNESS_KEY`.
  Ambos via env, sem fallback; ausencia estoura antes de tocar rede.
- Teto de 4 MB verificado antes de ler env ou abrir socket.
- `harness_commit` = `git rev-parse --short HEAD`, sem fallback.
- Antes de serializar, `varre_documento` (guarda) recusa o documento inteiro se
  qualquer string alcancavel contiver CPF ou e-mail.

## Documento (campo `versao`)

| versao | mudanca |
|---|---|
| 1 | `preflights[]` (C8/C9/C11 sobre `SpecCampanha`) e `leituras[]` (funil enviado -> entregue -> aberto -> clicado, vereditos C2/C3, achados) |
| 2 | aditivo: `riscos[]` (veredito agregado de risk squad: casa, squad, acao, janela, segmentos, cobertura, vies de selecao, achados de governanca) |
| 3 | `riscos[].cobertura_pct` passa de string para `{"valor", "rotulo"}`; `rotulo` em `medido` / `estimado` / `ausente` (`valor: null`) |

Versoes anteriores ficam congeladas; goldens em `tests/golden/documento_v1..v3/`.

## Invariantes

- Nenhum `player_id`/`user_ext_id` cruza a fronteira: so agregados.
- `proveniencia` fica em `resultados/` e nunca e enviada.
- `rotulo: "ausente"` deve ser tratado como "nao medido", nunca como zero.
