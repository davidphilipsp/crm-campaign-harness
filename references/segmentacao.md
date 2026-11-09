# segmentacao.md
> Conhecimento operacional de Segment Builder, propriedades de usuário e identificadores na Smartico.
> Destilado das conversas do projeto (mai–jul/2026). **Nenhuma afirmação de resultado de campanha entra aqui** — resultados medidos ficam fora deste repositório.

**Marcação de origem**
- `[doc oficial]` — rastreável até help.smartico.ai, resposta de API, payload ou tela do BackOffice
- `[testado por mim]` — validado no ambiente (print, erro real, query rodada, contagem conferida)
- `[suposição]` — inferência não confirmada. Inclui o que é canônico no PRD v1.0 mas nunca foi reconferido na doc da Smartico

---

## 1. Tipos de condição que aparecem nos segmentos reais

| Tipo | Como se comporta | Origem |
|---|---|---|
| **User State** | Propriedade estática do perfil (`Core: …`, `Accounting: …`). Avalia o valor atual. | `[testado por mim]` |
| **Behaviour / Time back period** | `User had activity · <evento> · in the past N Days`. **Janela rolante**, não fixa em dia da semana. | `[testado por mim]` |
| **Event attributes** | Atributo do evento (ex.: `Casino: Bet Game Name = AVIATOR`). Combináveis com OR. | `[testado por mim]` |
| **State based segments** | Pertencer / **não** pertencer a outro segmento (`has any of` / `doesn't have any of`). É como as blacklists são aplicadas. | `[testado por mim]` |

### 🔴 Conferir sempre o conector
A Smartico renderiza um resumo em texto embaixo das condições. Leia esse resumo antes de salvar: se o conector entre duas condições aparecer como **OR** onde deveria ser **AND**, o segmento **soma** as bases em vez de restringir. Já foi ponto de debug real. `[testado por mim]`

---

## 2. Propriedades usadas com frequência (e as armadilhas de cada uma)

| Condição na UI | Chave técnica | O que faz / armadilha | Origem |
|---|---|---|---|
| `Core: last time online` | `core_user_last_time_online` | Guarda **um único timestamp** do último momento online. Quem esteve online ontem **e** hoje cai em "hoje" e **sai** de um filtro de "ontem". Reportado com mais frequência que o login (refresh, navegação entre páginas). | `[doc oficial]` (comentário da própria propriedade no payload) + `[testado por mim]` |
| `Core: last login date` | `core_user_last_login` | Reportado **uma vez por sessão** — granularidade mais grossa que `last_time_online`. | `[doc oficial]` |
| Status online/offline | — | É estado **atual**, tempo real. Não serve para janela histórica ("ontem"). | `[suposição]` |
| `Accounting: Last Deposit Date is after <data>` | — | Janela de relacionamento financeiro. Data absoluta, não rolante — precisa ser atualizada a cada rebuild. | `[testado por mim]` |
| `Core: recommended deposit amount >= X` | — | Ticket sugerido calculado pela Smartico. É **piso, não teto** — `>= <valor>` captura de casual a VIP. | `[testado por mim]` |
| `Core: account status is not one of …` | — | Compliance. Valores observados na UI: `SUSPENDED`, `SELF_EXCLUDED`, `PENDING`, `LOCKED`, `DEACTIVATED`, `BLOCKED`, `BANNED`, `Not set`. | `[testado por mim]` |
| `Core: State based segments doesn't have any of …` | — | Blacklist (ex.: `Exclusão Disparo - SMS opt out / viciado / autoexcluded`). O segmento de exclusão já existe na base — só apontar para ele. | `[testado por mim]` |
| Gamification level (range de sub-níveis) | — | Ex.: Safira I → Royal X = 50 sub-níveis. Necessário quando o objeto comunicado (torneio/missão) só é visível para um range. | `[testado por mim]` |
| `Tournament: User Position` | — | **Pode não estar exposto nativamente.** Plano B: exportar o top N e excluir por lista. | `[suposição]` |
| Provider (ex.: PG Soft) como atributo | — | **Não confirmado** que a Smartico exponha Provider. Plano B: filtrar pelos game names mais jogados daquele provider. | `[suposição]` |

### 🔴 Timezone é decisão explícita
A Smartico trabalha tanto com dia-calendário em UTC quanto no fuso do usuário. "Ontem em UTC" ≠ "ontem no fuso do site". Escolha um e registre qual foi usado — senão o pool fica inconsistente entre rebuilds. `[suposição]`

### Como saber se uma propriedade está realmente populada
A Smartico **exibe propriedades nativas mesmo sem dado vindo da integração** — elas aparecem como `not set`. O teste de verdade é: criar um segmento com a propriedade e ler a contagem de usuários. Se vier zero/perto de zero, a integração não popula aquele campo. `[doc oficial]`

---

## 3. Procedimento padrão — construir e validar um segmento

1. Montar as condições no Segment Builder.
2. **Ler o resumo em texto** e conferir AND/OR (§1).
3. Clicar em **Estimate** e anotar o número.
4. Comparar com um número esperado antes de assinar:
   - voltou **igual ao segmento sem o filtro** → o filtro não está mordendo (atributo errado ou conector OR);
   - voltou **ordens de grandeza menor** → filtro rígido demais ou atributo errado;
   - voltou uma redução plausível → provavelmente correto.
5. Só então usar o segmento numa campanha.

`[testado por mim]` — esse loop de "estimar → comparar com expectativa → debugar" foi o que pegou erro de portão de recência.

**Onde ler a audiência:** `Segments → selecionar segmento → Audience size`. `[doc oficial]` (PRD §3.8)

---

## 4. Extrair a lista de usuários de um segmento

- Caminho limpo: **Export segment → CSV** — entrega o pool **completo**. `[testado por mim]`
- Captura via Network XHR / DOM no DevTools do navegador pega **apenas a página visível** — não serve para pool completo. Só usar se a role não tiver permissão de export. `[testado por mim]`
- O formato "IDs separados por vírgula" cola direto num filtro `user_id is one of` de um segmento de teste. `[testado por mim]`
- Para sortear N usuários de um pool: usar Fisher–Yates. `ids.sort(() => Math.random() - 0.5)` **enviesa** a amostra (não é uniforme) — é fato de estatística, não comportamento do Smartico. `[testado por mim]`

### 🔴 LGPD
`user_id` / Ext. ID são dado pessoal. Usar só na finalidade autorizada, não persistir em docs ou planilhas compartilhadas, manter dado individual em CSV separado do relatório agregado. `[suposição]`

---

## 5. Segmentos dinâmicos vs estáticos

| | Dinâmico (User State / Behaviour) | Estático (lista) |
|---|---|---|
| Onde nasce | Query builder da UI | Import de CSV |
| API | **Não existe API** para criar/editar | Upload manual na UI |
| Manutenção | Recalcula sozinho | Precisa de regeração periódica |
| Formato do CSV | — | delimitador `;`, encoding UTF-8-sig |

`[suposição]` na parte de "não existe API" — foi conclusão do mapeamento de automações, não confirmada por escrito com a Smartico.

Quando usar estático: critério que não cabe no query builder (janela calculada, cruzamento com dado externo/BetMetrics). `[suposição]`

---

## 6. Modelos nativos de segmentação

### RFM
- Calculado sobre a atividade dos **últimos 30 dias** (depósito **ou** aposta, conforme a metodologia escolhida). Ranqueia R/F/M numa escala que vira códigos de 3 dígitos. `[doc oficial]`
- **Champions:** `555, 554, 544, 545, 454, 455, 445` `[doc oficial]`
- **Potential Loyalist:** `553, 551, 552, 541, 542, 533, 532, 531, 452, 451, 442, 441, 431, 453, 433, 432, 423, 353, 352, 351, 342, 341, 333, 323` — note que vários são R3 (recência média). `[doc oficial]`

### Churn prediction
- 🔴 **As predições são atualizadas diariamente** — o score/rank é batch diário, não recalculado por evento. `[doc oficial]`
- O evento `Core: churn prediction updated` dispara quando o **rank muda** entre avaliações diárias. Ou seja: a "entrada real-time" é real-time no mecanismo de matrícula, mas o sinal em si tem latência de 1 dia — mesma latência de um sweep diário próprio. `[doc oficial]`
- Usa **thresholds fixos e uniformes** (7/14/30d por operador), iguais para todo mundo. **Não normaliza por cadência individual do jogador.** `[doc oficial]`

### Value Score
Existe como modelo nativo. Não foi explorado no projeto. `[doc oficial]` (só a existência)

---

## 7. Identificadores — o que é cada um (fonte recorrente de erro)

| Identificador | O que é | Onde vive | Origem |
|---|---|---|---|
| `ext_brand_id` | ID da sua marca **no seu próprio sistema (PAM)**, definido na integração. String ou inteiro. **Não** é gerado nem escondido em menu da Smartico. | Payloads de evento, integração de dados, setups multi-brand | `[doc oficial]` |
| `brand_key` | Chave **pública** da marca | Front-end: `_smartico.init(...)` | `[doc oficial]` |
| `label_key` | Chave pública do label | Front-end, junto com `brand_key` no `init` | `[doc oficial]` |
| `label_id` | ID do label | Aparece no nome do usuário do BigQuery, formato `dwh_ext_1234` | `[doc oficial]` |
| `user_ext_id` | ID do usuário no seu sistema | Payload de API | `[doc oficial]` |

### 🔴 Três armadilhas confirmadas
1. **`label ≠ brand`.** Um label pode conter várias marcas. `labelId` (interno) **não** é o `ext_brand_id`. `[doc oficial]`
2. **O BackOffice exibe o Ext. ID com prefixo `<prefixo>:`, mas a API espera o ID sem o prefixo.** Enviar `<prefixo>:<user_ext_id>` retorna `err_code 2` / "User not found"; enviar `<user_ext_id>` funciona. O `<prefixo>:` é artefato de apresentação (provavelmente identificador de label/brand na camada de display). `[testado por mim]` + `[suposição]` na explicação do porquê
3. **Eventos de login não carregam `ext_brand_id`.** Vêm do SDK de front-end (`source_server_type: "CHANNEL"`), que se autentica por `label_key`/`brand_key` e resolve tudo para o `labelId` interno. O campo literal só aparece em eventos reportados **a partir do PAM** (depósitos, `update_profile`, eventos via API). `[testado por mim]`

**Onde confirmar o `ext_brand_id` real que está trafegando:** BackOffice → `CRM` → buscar usuário pelo User ext ID → aba **Events** → expandir um evento → o raw payload é exibido do lado esquerdo. `[doc oficial]`

**Fonte autoritativa das chaves de propriedade da sua instância:** `Tools → REST API` (lista as tags) + as tags do Segment Builder. Tratar resposta de IA/doc genérica como rascunho e cruzar com o BO. `[doc oficial]`

---

## 8. Padrão mínimo de exclusão em qualquer segmento de disparo

Cinco condições que apareceram como "obrigatórias" nos segmentos maduros da base:

1. Critério de comportamento/valor (o que define o público de fato)
2. Filtro de recência (evita queimar crédito em quem não loga)
3. Range de nível compatível com o objeto comunicado (senão o jogador clica e vê conteúdo bloqueado)
4. `Core: account status is not one of (…)` — compliance
5. `State based segments doesn't have any of (Exclusão Disparo - SMS opt out / viciado / autoexcluded)` — blacklist

`[testado por mim]` — extraído da leitura de segmentos reais de torneio.

> ⚠️ O filtro de blacklist do segmento é **SMS-focado** na base atual. Um flow de e-mail **não** herda proteção de e-mail dele — precisa do gate próprio no `check_user_profile` (ver `flow.md` §7). `[testado por mim]`

---

## 9. Anti-sobreposição entre segmentos

Quando dois segmentos disparam na mesma janela, excluir um do outro (`doesn't have any of`) para que o jogador que qualifica nos dois receba **um** disparo, não dois. Padrão já em uso na base. `[testado por mim]`

---

## 10. Pendências abertas de segmentação

| # | O que confirmar | Onde |
|---|---|---|
| 1 | Nomes exatos das chaves marcadas `(a confirmar)` no mapa de propriedades | User State / Segment Builder / `Tools → REST API` |
| 2 | Existe chave nativa de "próximo nível / pontos exigidos"? (o GAP do cálculo de %) | User State |
| 3 | Provider é exposto como atributo de evento? | Segment Builder |
| 4 | `Tournament: User Position` é filtrável nativamente? | Segment Builder |
| 5 | Timezone padrão adotado pela operação para janelas de "ontem/últimos N dias" | Decisão interna, ainda não registrada |
