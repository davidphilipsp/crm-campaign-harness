# flow.md
> Conhecimento operacional de Journeys, Automation Rules, nós, entry modes, triggers e o gate de compliance.
> Destilado das conversas do projeto (mai–jul/2026). **Nenhuma afirmação de resultado de campanha entra aqui** — resultados medidos ficam fora deste repositório.

**Marcação de origem**
- `[doc oficial]` — rastreável até help.smartico.ai, resposta de API, payload ou tela do BackOffice
- `[testado por mim]` — validado no ambiente (print, erro real, query rodada)
- `[suposição]` — inferência não confirmada. Inclui o que é canônico no PRD v1.0 mas nunca foi reconferido na doc

---

## 1. Os quatro objetos de ativação — quem faz o quê

| Objeto | Disparado por | **Envia comunicação?** | Aceita tags de `event`? |
|---|---|---|---|
| **Journey · Realtime** | Evento | 🟢 Sim | 🟢 Sim |
| **Journey · Scheduled (campaign)** | Horário | 🟢 Sim | 🔴 **Não** (lote, sem contexto de evento) |
| **Automation Rule · Realtime** | Evento | 🔴 **Não** | Só em WebHook/Slack |
| **Automation Rule · Scheduled** | Horário | 🔴 **Não** | — |

`[doc oficial]`

**Consequências práticas:**
- **Automation rule não envia nada.** É o melhor "ouvinte" (extremamente performática, executa milhares de ações simples em segundos, roda WebHook), mas o envio precisa de Journey. `[doc oficial]`
- Se o conteúdo vem de fora, o desenho exige **dois objetos**: Automation Rule capta + WebHook out; Journey Realtime envia. `[doc oficial]`
- Em **Scheduled Campaign**, atividade que exige usuário online **não pode ser o primeiro passo**. `[doc oficial]`

---

## 2. Entry modes

### Nomenclatura — atenção à divergência
Existem **dois vocabulários** circulando no projeto, e eles não foram reconciliados:

| Vocabulário do PRD v1.0 | Vocabulário do DWH (`dm_audience.entry_mode_id`) | Vocabulário visto na UI |
|---|---|---|
| Run one at a time | `3` = STOP_AND_START (?) | — |
| Run few at the same time | — | — |
| Only once per user (lifetime) | `0` = ONCE_IN_A_LIFE | Once ever |
| Only once per user per period | — | — |
| — | `1` = ONCE_IN_AN_OPEN_JOURNEY | Once during open journey |
| — | `2` = EVERY_TIME_CONDITION_MET | Every time / Every time conditions are met |

🔴 **O mapeamento entre as colunas acima é `[suposição]` minha.** Só `entry_mode_id 0–3` é `[doc oficial]` (dicionário do DWH) e "Once during open journey / Every time / Once ever" é `[testado por mim]` (visto na UI). **Antes de usar essa tabela como referência, confirme o nome exato na sua tela.**

### Regra de decisão (canônica no PRD, não reconferida na doc)

| Entry mode | Usar quando | Evitar quando |
|---|---|---|
| Run one at a time | Trigger de alta frequência por usuário (compra, aposta); risco de execuções paralelas conflitantes; flow com Multiple Check que depende do evento mais recente | Eventos esparsos por natureza |
| Run few at the same time | Trigger naturalmente espaçado (`level changed`, `first deposit`); flow sequencial; duração curta (<1 dia) | Compras/apostas em sequência |
| Once per user (lifetime) | Onboarding, FTD, marcos únicos | Comunicação recorrente |
| Once per user per period | Recompensa diária/semanal, check-in | Triggers determinísticos irrepetíveis |

`[suposição]` — PRD §3.3, não reconferido na doc da Smartico.

### Comportamento de re-entrada (Realtime)
O usuário **re-entra toda vez que as condições são atendidas** — a instância anterior é terminada e uma nova começa. Exceção: once-per-lifetime / once-per-period. `[doc oficial]`

### Dois casos concretos resolvidos no projeto `[testado por mim]`

**Caso A — journey de progressão (M1→M2→M3) com Multiple Check como controlador de estado.**
`Once during open journey` **quebra** o desenho: o usuário entra uma vez, é roteado para o ramo do estado atual, e não volta para receber as comunicações seguintes. Precisa de entry mode que permita reentrada (`Every time`), porque o Multiple Check é quem garante que ele recebe a mensagem certa — o entry mode só garante que ele **pode voltar**.

**Caso B — journey de apresentação de missão do dia.**
`Once during open journey` + `Max duration = 1 Day` resolve o anti-reenvio **sem** Limit e sem condição extra: o usuário entra uma vez no dia, ponto.

**Regra que sai desses dois:** uma journey que tenta *apresentar* e *reagir* ao mesmo tempo cria conflito de trigger. Separar em duas journeys, cada uma com um trigger limpo. `[testado por mim]`

---

## 3. Nós do flow — o que cada um faz e o que quebra

| Nó | Comportamento | Armadilha | Origem |
|---|---|---|---|
| **Multiple Check** | Roteia por condição. É o controlador de estado do flow. | 🔴 **Sem rota default, quem não casa com nenhuma banda cai no vazio.** Causa observada de "convertido que não recebeu o prêmio". | `[testado por mim]` |
| **Wait for event** | Espera um evento + condição. Campos: `Event to wait`, condição, `Maximum time to wait`. | 🔴 **O padrão do sistema é 5 minutos.** Sempre sobrescrever — regra interna: nunca menos de 24h para ação que exige depósito + jogo. | `[testado por mim]` |
| **Delay / Delay Till** | Espera por tempo. `Delay Till` suporta fuso do usuário. | — | `[doc oficial]` |
| **Check user profile** | Gate de elegibilidade. **Avaliação única** (não re-avalia depois). | Ver §7 | `[doc oficial]` |
| **Limit** | 🔴 **É limite GLOBAL de volume, não por usuário.** Para controle por usuário, usar condição no Multiple Check. | Erro clássico: achar que "Limit 1" trava reenvio por pessoa. | `[testado por mim]` |
| **Funnel Marker** | Marca etapa do funil. | Precisa estar em **todos** os ramos do Multiple Check, senão o funil fica cego naquele braço. | `[testado por mim]` |
| **Control Group (%)** | Holdout nativo em Campaign. | Ver §8 — o holdout pode existir e mesmo assim ficar cego. | `[doc oficial]` |
| **WebHook** | Chamada HTTP de **saída**. Config: URL, Method (POST recomendado, GET também), headers adicionais, body JSON com `{{state.*}}` e `{{event.*}}`. Existe serviço de echo para testar o que foi enviado. | 🔴 **A resposta do seu endpoint NÃO volta ao flow como variável.** Não existe "webhook busca → próximo nó usa". | `[doc oficial]` |
| **Gamification** | Entrega/ativa missão dentro do flow. | — | `[testado por mim]` |
| **Convert campaign** | Marca conversão. | 🔴 Ver §8 — quem está no control group **não percorre o flow**, logo nunca chega nesse nó. | `[testado por mim]` |
| **Max campaign duration** | Teto de duração por instância. | 🔴 Conferir contra a **soma real** dos delays do flow. Achado de auditoria real: `Max duration = 1 Day` num flow que somava 19h + 19h + delays de fim de semana. | `[testado por mim]` |

---

## 4. Triggers e eventos — nomes reais

| Objetivo | Evento correto | Evento errado / observação | Origem |
|---|---|---|---|
| Usuário abriu o site/app | `Core: user went online` | — | `[testado por mim]` |
| Usuário **completou** missão | `Gamification: mission completed` + condição `Gamification: last completed mission name` = **nome exato da missão** | 🔴 `Gamification: mission unlocked` — ver §5 | `[testado por mim]` |
| Usuário apostou | `Casino: Bet-Win` | `Casino: Bet` conta apostas, não o par aposta-ganho | `[testado por mim]` |
| Mudança de nível | `level changed` / `Gamification: level upgrade` | ⚠️ Os dois nomes aparecem em conversas diferentes — **confirmar qual existe de fato** na sua instância | `[suposição]` |
| Compra na loja | `Core: store purchase succeeded` | — | `[suposição]` (PRD, não reconferido) |
| Evento server-to-server com parâmetros | `Core: client action` — capturável por Wait for Event | — | `[doc oficial]` |
| Injetar conteúdo externo e disparar envio nativo | `Core: send personal message` | — | `[doc oficial]` |
| Mudança de rank de churn | `Core: churn prediction updated` (batch diário) | — | `[doc oficial]` |
| Depósito aprovado (conversão) | `Acc: Deposit Approved` | — | `[testado por mim]` |

---

## 5. 🔴 O bug de missão que custou debug (guardar)

**Sintoma:** a M1 nunca aparecia no `Wait for event` e o flow não avançava.

**Duas causas encadeadas:**

1. **Tipo da missão errado.** A M1 estava como `Generally available`, que significa "aparece para **todos os usuários da plataforma**, sem segmentação" — ela existe fora do contexto do segmento do flow. O correto é `Available, Unlocked`: desbloqueada, mas **dentro** da segmentação configurada. `[testado por mim]`

2. **Evento errado.** `Gamification: mission unlocked` **nunca dispara** para uma missão que nasce `Available, Unlocked` — não existe um momento de "desbloqueio" para ela. Trocar para `Gamification: mission completed`, que dispara na conclusão das tasks independentemente do tipo da missão. `[testado por mim]`

**Configuração correta do Wait for event:**
```
Event to wait:        Gamification: mission completed
Condição:             Gamification: last completed mission name = <nome exato da missão>
Maximum time to wait: 24 Hours   (nunca os 5 min do padrão)
```

---

## 6. Configuração de missões (o que cada campo faz)

### Tipos de missão
| Tipo | Comportamento | Origem |
|---|---|---|
| `Generally available` | Visível para **toda a plataforma**, ignora segmentação | `[testado por mim]` |
| `Available, Unlocked` | Desbloqueada, **dentro** da segmentação | `[testado por mim]` |
| `Available, Locked` | Visível mas travada; desbloqueia por condição (ex.: missão anterior concluída) | `[testado por mim]` |

**Trava progressiva:** M1 `Unlocked` → M2 `Locked` (condição: M1 concluída) → M3 `Locked` (condição: M2 concluída). `[testado por mim]`

**Ao clonar missões:** ativar `Copy Tasks` e `Copy Related Games`, senão jogos e condições não vêm junto. `[testado por mim]`

### Campos de uma task
`Task name` · `Task type` (ex.: *Complete action once* / *Complete action a few times, check SUM of attribute*) · `Action` (ex.: `Casino: Bet-Win`) · `Calculate total values of` (ex.: `Casino: Last Win Amount`) · `Total amount should reach` · `How often counted` (`Not limited` = todos os eventos contam) · `Period to complete` · condições (ex.: `Casino: Bet Game Type = SLOTS`). `[testado por mim]`

### 🔴 Valores monetários e a divergência de 100x
Um campo configurado com `200.000` foi lido pelo sistema como **2.000,00** enquanto o nome da task dizia "Some 200.000" — ou seja, o campo estava em **centavos**. `[testado por mim]` que a divergência existiu; `[suposição]` que "valores monetários são sempre em centavos" — **isso nunca foi confirmado na doc.** Procedimento: em toda task nova, conferir se o valor bate com a intenção antes de publicar.

### Outros pontos de atenção
- `Win Amount (Real)` usa saldo real, não bônus. Ganho com bônus não completa a task. `[testado por mim]`
- Task amarrada a um jogo específico não é completável em outro slot, por maior que seja o ganho. `[testado por mim]`
- Task sem período definido não expira sozinha — o controle de prazo tem que estar **na missão**, não na task. `[testado por mim]`

---

## 7. Gate de compliance — `Check user profile`

**Quatro condições mínimas antes de qualquer envio:**

| # | Condição | Cobre |
|---|---|---|
| 1 | `Core: smartico email status (internal)` **is not one of** → `Not set`, `BLOCKED`, +N ocultos | E-mail bloqueado internamente |
| 2 | `Core: is email opted out (Smartico)` = `False` | Opt-out Smartico |
| 3 | `Core: Is email opted out on integrated PAM` = `False` | Opt-out no PAM do operador |
| 4 | `Core: External Account status` **is not one of** → `Not set`, `AML_FRAUD`, `DELETED`, `BANNED`, `SUSPENDED`, `CLOSED` | AML/fraude, banimento, exclusão |

`[doc oficial]` para a existência das condições; a lista de valores da #4 é `[testado por mim]` (lida na tela).

### 🔴 Três regras que já pegaram erro real
1. **"+N valores ocultos" precisa ser expandido e auditado.** Presumir que `DELETED`/`BANNED`/`SUSPENDED` estão incluídos sem verificar é falha de compliance. `[doc oficial]` (regra do PRD) + `[testado por mim]` (flow real estava incompleto)
2. **Coerência de canal.** Num flow de **e-mail**, a condição 3 tem que ser opt-out de **e-mail** no PAM — não de SMS. Um flow de teste real estava com a condição errada. `[testado por mim]`
3. **A blacklist do segmento não substitui o gate.** A exclusão de entrada em uso na base (`Exclusão Disparo - SMS opt out / viciado / autoexcluded`) é SMS-focada; e-mail exige as 4 condições no nó. `[testado por mim]`

**Posição no flow:** o gate fica **antes** da activity de envio. Como o envio é nativo, ele herda opt-out + caps da própria activity. `[doc oficial]`

---

## 8. Control group — como funciona e por que ele fica cego

**O que a doc diz:** usuários do control group registram `activity_type_id` **1 (entrada), 2 (parada) e 3 (conversão)** — eles entram, param e **podem converter**, mas não percorrem o fluxo. É isso que torna a medição de incrementalidade possível. `from_control_group = NULL` significa **fora** do controle. `[doc oficial]`

**🔴 O que descobrimos na prática:** numa campanha real com holdout bem desenhado (21%), o control group registrou **zero conversões**. A causa não é falta de tracking — é que **aquela campanha marca conversão com um nó `Convert campaign` dentro do flow**, e quem está no controle nunca chega ao nó. `[testado por mim]`

**Correção:** medir conversão do controle por `j_av` e/ou `r_deposits` / `tr_acc_deposit_approved` — que são por evento e não dependem de percorrer nós. O holdout existe e é utilizável, só não pelo caminho óbvio. `[testado por mim]`

---

## 9. Ordem de operação: creditar antes de notificar

Quando o flow credita um bônus e notifica, **credite primeiro, notifique depois**. Caso real: 89 bônus foram concedidos a usuários cuja notificação falhou — o custo saiu e o jogador nunca soube. `[testado por mim]`

O valor citado na mensagem deve vir de tag dinâmica puxando o crédito real, não de texto fixo. `[suposição]`

---

## 10. REST API — o que está validado

**Endpoint que funciona:** `https://apis<N>.smartico.ai/api/external/events/v2`
🔴 `https://apis.smartico.ai/...` (o exemplo genérico da doc pública) devolveu `errCode 10000`. O subdomínio é específico do ambiente. `[testado por mim]`

```bash
curl -s --request POST \
  --url 'https://apis<N>.smartico.ai/api/external/events/v2' \
  --header "Authorization: ${SMARTICO_KEY}" \
  --header 'Content-Type: application/json' \
  --data '[{
    "eid":"test-<uuid>",
    "event_date":<epoch>000,
    "ext_brand_id":"<seu-brand-id>",
    "user_ext_id":"<id sem prefixo <prefixo>:>",
    "event_type":"core_personal_message",
    "payload":{"channel":"email-api"}
  }]'
```

| Código / mensagem | Significa | Origem |
|---|---|---|
| `errCode 10000` | Falha de autenticação — key errada **ou subdomínio errado** | `[testado por mim]` |
| `err_code 2` + "User … was not found" | Auth passou; o `user_ext_id` literal não existe (normalmente prefixo `<prefixo>:` indevido) | `[testado por mim]` |
| "create user with `update_profile` event before reporting any other activities" | 🔴 **Usuário precisa existir na Smartico antes de receber qualquer evento.** Conta nova exige `update_profile` antes de `core_personal_message`. | `[doc oficial]` (mensagem da própria API) |

**Onde pegar a private key:** BackOffice → `Tools → REST API`, ou com o Success Manager. `[doc oficial]`

**Não existe API para criar/editar journeys.** A montagem no Flow Builder é manual — o que se automatiza é spec, revisão e auditoria. `[suposição]`

### O bridge `Core: send personal message`
Permite disparar comunicação a partir de fora, com personalização, usando as Journeys do BO para o envio. `[doc oficial]`
- Pré-requisito: criar a **Journey + Message Template** no BO antes; os **nomes das tags do template têm que bater exatamente** com os campos do payload. O HTML da área de mensagem vira o **base layout** de tudo enviado via API.
- Journey: trigger `Core: send personal message`, canal `Core: personal message channel` = ex. `email-api`, entry mode "every time conditions met", duração ~1 min.
- 🟡 Você injeta **campos/tags**, não um HTML fechado. HTML monolítico num único campo é frágil (escaping, JSON, limite de tamanho) — **não confirmado** se o Liquid renderiza HTML cru ou escapa.

---

## 11. Checklist antes de publicar uma journey

- [ ] Entry mode correto para o objetivo (e reentrada compatível com o desenho)?
- [ ] `Maximum time to wait` ≥ 24h em **todos** os `Wait for event`? (nunca os 5 min padrão)
- [ ] `Wait for event` com o **evento certo** (`mission completed`, não `mission unlocked`)?
- [ ] Nome da missão preenchido **exatamente** como cadastrado?
- [ ] Multiple Check tem **rota default**?
- [ ] Multiple Check com condições suficientes para evitar reenvio (se entry mode = Every time)?
- [ ] Funnel Marker em **todos** os ramos?
- [ ] `Check user profile` com as 4 condições, "+N ocultos" expandidos, canal coerente?
- [ ] `Max campaign duration` ≥ soma real dos delays do flow?
- [ ] Control group definido (se a campanha precisa de leitura de incrementalidade)?
- [ ] Conversão marcada de forma que o controle também seja mensurável (§8)?
- [ ] Segmento correto e com audience size conferido?
- [ ] Missões referenciadas existem, estão **ativas** e com o **tipo** correto?
- [ ] Testado em usuário de QA antes de ativar?
- [ ] Nome do asset em padrão de produção (nada de "Teste- …")?

`[testado por mim]` — consolidado de dois checklists usados no projeto.

---

## 12. Antipadrões confirmados

| # | Antipadrão | Consequência |
|---|---|---|
| 1 | Journey única fazendo apresentação **e** progressão de missões | Conflito de trigger e entry mode; reenvio ou mensagem fora de ordem |
| 2 | `Wait for event` com os 5 minutos padrão | Flow encerra antes do usuário ter tempo de depositar e jogar |
| 3 | Usar `Limit` achando que é limite por usuário | Não trava reenvio individual |
| 4 | Multiple Check sem rota default | Convertido sem prêmio |
| 5 | `mission unlocked` para detectar conclusão | Evento nunca dispara em missão `Available, Unlocked` |
| 6 | Missão como `Generally available` dentro de flow segmentado | Missão vaza para toda a base e não casa com o flow |
| 7 | Publicar sem testar em usuário de QA | — |
| 8 | Assumir que webhook devolve dado ao flow | Desenho impossível |

`[testado por mim]`
