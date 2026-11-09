# mensageria.md
> Conhecimento operacional de canais (SMS, e-mail, RCS, on-site), assets, personalização Liquid e tracking.
> Destilado das conversas do projeto (mai–jul/2026). **Nenhuma afirmação de resultado de campanha entra aqui** — resultados medidos ficam fora deste repositório.

**Marcação de origem**
- `[doc oficial]` — rastreável até help.smartico.ai, resposta de API, payload ou tela do BackOffice
- `[testado por mim]` — validado no ambiente (print, erro real, contagem conferida)
- `[suposição]` — inferência não confirmada. Inclui o que é canônico no PRD v1.0 mas nunca foi reconferido na doc

---

## 1. Onde cada coisa é configurada

| Item | Caminho | Origem |
|---|---|---|
| Gateways de SMS / instant messages | `Label → Gateways → Instant Messages` | `[doc oficial]` |
| Assets de instant message (SMS, RCS) | `Instant messages → Create/Edit` | `[testado por mim]` |
| Chave privada da REST API | `Tools → REST API` | `[doc oficial]` |
| Métricas de journey | `Journeys → selecionar journey → Analytics` | `[suposição]` (PRD §3.8) |

**Provedoras:** mais de 80 integradas nativamente (Karix, Twilio, Wavix e outras). Se a sua não está na lista, dá para pedir integração via JIRA com link do gateway e credenciais de teste. Alternativa: **Custom Gateway**, em que a Smartico chama a sua API para enviar e acompanhar status. `[doc oficial]`

🔴 **Pegadinha do Custom Gateway:** ele troca apenas o **transporte**. A Smartico continua renderizando o corpo a partir do asset — **não dá para injetar um corpo externo por ele**. `[doc oficial]`

**Reverse integration:** a Smartico pode notificar seu sistema por chamada HTTP toda vez que envia um asset, permitindo rastrear as comunicações em tempo real. Disponibilidade depende do plano — a confirmar. `[doc oficial]`

---

## 2. Modelos de asset de e-mail — a regra que define tudo

| Asset | O que renderiza | Limitação | Origem |
|---|---|---|---|
| **Liquid + HTML** | Dados escalares via tags de `state`, `campaign`, `event` | 🔴 **NÃO renderiza UI Widgets** — a doc afirma textualmente que "Liquid Email templates do not support UI Widgets" | `[doc oficial]` |
| **UI Widget** (em e-mail HTML) | Gera o próprio HTML para **listas/coleções** | Tem limite por tier de **MAU**, o que exige controle de taxa de envio em Scheduled | `[doc oficial]` |

### 🔴 A regra de ouro das coleções
Missões, torneios e badges **não são `state` escalar**. Não existe `{{state.torneios}}`.
- **Escalares** (nome, saldo, nível, contagem) → **Liquid email**
- **Listas** (torneios disponíveis, missões completadas na semana/hoje/mês, top 5 do leaderboard, mini-games com giros) → **HTML email + UI Widget**

`[doc oficial]`

**Casos de uso citados pela própria documentação:** lista de itens da Loja que o jogador pode pagar agora; todas as missões completadas no mês corrente; lobby + regras de um torneio específico; top 5 do leaderboard semanal; mini-jogos onde o jogador tem giros disponíveis. `[doc oficial]`

### Tags
- Funcionam em e-mail Liquid: `{{state.*}}`, `{{campaign.*}}`, `{{event.*}}`
- **Tags de `label`: fontes divergem.** Não confirmado se funcionam em e-mail Liquid. Isso decide se T&Cs/links via `label` servem no canal. `[suposição — pendência aberta]`
- `{{event.*}}` só existe em journey **disparada por evento**. Não funciona em scheduled campaign nem em automation rule. `[doc oficial]`
- Formatação de data: `{{ state.last_deposit_date | date: "%d/%m/%Y" }}`; ajuste de fuso somando segundos. `[doc oficial]`
- **Campaign tags** persistem valores de `state`/`event` durante a execução da journey. `[doc oficial]`

### Gateway de e-mail
Email activity nativa (SendGrid). Herda **opt-out, caps, A/B e Best Time**. Em multi-brand, a marca é resolvida por **Automatic Selection** (condição default = Brand) + `{{state.core_sm_brand_id}}`, com override do 'from' name. `[doc oficial]`

### O que a doc **não** responde sobre SMS/WhatsApp/Push
A página de widgets é silenciosa sobre se esses canais aceitam personalização Liquid básica (nome, tier, saldo). É quase certo que aceitem **placeholders simples**, mas não a lista dinâmica dos widgets. Três perguntas a cobrar por escrito do CSM: `[doc oficial]` que a lacuna existe
1. SMS/WhatsApp/Push aceitam tags Liquid para campos do usuário?
2. Algum deles aceita lista dinâmica via shortcode?
3. Existe limite de comprimento para conteúdo dinâmico nesses canais?

---

## 3. Liquid Sections (widget on-site)

> ⚠️ Tudo nesta seção é **canônico no PRD v1.0** e **não foi reconferido na doc da Smartico** nem testado end-to-end nas conversas do projeto. Tratar como `[suposição]` até validar com um render real.

**Tipos disponíveis:** HTML livre, Custom Levels UI, Missions, Tournaments, Mini-games, Lootbox.

**Injeção de dados assumida em qualquer section de clube de fidelidade:**
```html
<script id="data-user"        type="application/json">{{ userInfo        | json }}</script>
<script id="data-missions"    type="application/json">{{ missions        | json }}</script>
<script id="data-badges"      type="application/json">{{ badges          | json }}</script>
<script id="data-store"       type="application/json">{{ storeItems      | json }}</script>
<script id="data-categories"  type="application/json">{{ storeCategories | json }}</script>
<script id="data-tournaments" type="application/json">{{ tournaments     | json }}</script>
<script id="data-minigames"   type="application/json">{{ minigames       | json }}</script>
<script id="data-levels"      type="application/json">{{ levels          | json }}</script>
```

**Paths com fallback em cadeia (nunca confiar num campo só):**
- Nome: `displayName || full_name || username || firstName`
- Nível atual: `ach_level_current || currentLevel.name || level.key`
- Pontos: `ach_points_ever || ach_points_balance || points || xp`
- Próximo nível: `ach_level_next || nextLevel`

**Navegação interna (deep links):** `dp:gf_tournaments` (torneios) · `dp:gf_bonuses` (loja) · `dp:gf_saw` (roleta/mini-games).
**APIs do widget:** `openMission(id)`, `openTournament(id)`, `openBadge(id)`, `openStore(id)`.

**Regras obrigatórias de código:**
- `escapeHtml()` em **todo** conteúdo dinâmico renderizado
- fallback em cadeia sempre
- testar com `userInfo = {}` como edge case
- mobile-first, breakpoints 420/640/768/1040
- limpar listeners; sem memory leak em `setInterval`
- `alt` em imagens, contraste, `aria-label` em botões-ícone
- tratar estado vazio e garantir que o loader some

### 🔴 O GAP do "% para o próximo nível"
Para calcular `pontos_atuais ÷ pontos_exigidos_próximo_nível × 100` faltam **o próximo nível** e os **pontos exigidos**. Essas chaves **não estão confirmadas**. Enquanto não estiverem: não usar barra de progresso em Liquid, ou usar **tabela fixa de limiares** (mais frágil, mas honesta). `[suposição — pendência aberta]`

---

## 4. SMS — engenharia da mensagem

### Encoding (padrão GSM, não comportamento da Smartico)
| Encoding | 1 segmento | Concatenado |
|---|---|---|
| **GSM-7** | 160 chars | 153 chars/segmento |
| **UCS-2** | 70 chars | 67 chars/segmento |

🔴 **Um único caractere acentuado (ç, ã, é, ô…) força UCS-2 e derruba o limite de 160 → 70.** É o erro mais caro do canal. `[doc oficial]` (padrão GSM) + `[testado por mim]` (medido nas copies reais)

O caractere `|` está fora do alfabeto GSM-7 básico e custa **2 septetos**. Trocar por `-` ou `.` zera esse acréscimo — mas alterar advertência legal exige aprovação do jurídico. `[testado por mim]`

### Orçamento de caracteres
Elementos fixos consomem ~35 chars antes de qualquer copy:
`MARCA: ` (7) + `(+18)` (5) + link curto rastreável `https://5.brws.vc/xxxxxx` (~24).
Sobram ~125 chars para gancho + corpo + CTA dentro de 1 segmento.
Alternativa ao link curto: domínio limpo `brand-a.example` (11 chars), quando não precisa de atribuição granular. `[testado por mim]`

*Afirmações sobre desempenho de copy são hipóteses e ficam fora deste repositório.*

### Estrutura de 6 blocos (ordem observada, nunca quebrada)
```
MARCA: [GANCHO]! [Nome,] [contexto + oferta + jogo]. [CTA imperativo] (+18): [link]
```
1. **MARCA** `MARCA:` (nome da marca) — sempre
2. **GANCHO** — um só, nunca empilhar: urgência **ou** número grande **ou** status/evento
3. **NOME** — opcional, logo após a marca ou embutido no gancho
4. **CORPO** — o quê + onde + mecânica
5. **CTA** — verbo no imperativo (`Acesse`, `Entra`, `Confere`, `Jogue`, `Veja`, `Complete`)
6. **COMPLIANCE + LINK** — `(+18)` colado ao link, que sempre fecha

`[testado por mim]` (engenharia reversa de 8 copies reais)

### Regras linguísticas observadas
Zero acento e cedilha · abreviações informais (`vc`, `ta`) · CAPS seletivo em 2–4 palavras-chave · imperativo no CTA · 1–2 exclamações · diminutivo afetivo (`rodadinhas`) · números redondos grandes como `40 MIL`, precisos com ponto de milhar `100.000` · fragmentos curtos em vez de frases completas. `[testado por mim]`

### Compliance BR no SMS
`(+18)` · advertência de jogo responsável · URL `.bet.br` · sem urgência fabricada · sem promessa de ganho fácil ou garantia · sem condicionar benefício a depósito quando a peça diz que não condiciona · nunca mirar menor de idade. Lei 14.790/2023 + Portaria SPA/MF — **revisão jurídica antes de publicar**. `[suposição]` na formulação exata; o enquadramento legal é `[doc oficial]` público.

Para reativação: garantir **no nível da lista**, não do texto, que a base exclua autoexclusão e sinalizados em jogo responsável. `[suposição]`

---

## 5. Tracking de clique — o que é pré-requisito

🔴 **A Smartico só rastreia o clique se o SMS sair através da Smartico**, com a provedora configurada como gateway. Disparo direto na plataforma da provedora não gera fato de clique. `[doc oficial]`

**Do lado da provedora, o não-negociável:**
- estar integrada como gateway na Smartico;
- **devolver DLR** (status de entrega, incluindo bounces) — é isso que popula `SENT`, `DELIVERED` e `FAIL`;
- entregar o corpo **sem alterar ou quebrar o short link**, senão o redirect (e o clique) não funciona.

`[doc oficial]`

**Do lado da sua infra:**
- **Branded Links** — configurações `Short URL Domain` e `Deep link path of the label website`;
- apex (`dominio.bet.br`) exige ALIAS/ANAME/CNAME flattening; subdomínio é mais simples;
- proxy com SSL válido se o short link for HTTPS;
- **script da Smartico instalado no site** para executar o deep-link após o login.

`[doc oficial]`

**Onde o clique aparece no dado:** `j_communication`, `fact_type_id = 4` (CLICK), e o campo `fact_details` guarda **o link exato clicado**. No perfil do usuário ficam materializados `sms_last_clicked_date` e `last_marketing_sms_sent_date` — utilizáveis como state tags em segmentação e journeys. `[doc oficial]`

### Três ressalvas de leitura
1. Fatos de comunicação são rastreados por **apenas 30 dias** após a criação — clique tardio pode não entrar. `[doc oficial]`
2. Problemas na provedora geram **registros duplicados** para a mesma mensagem. Usar sempre `DISTINCT`/`QUALIFY` em `communication_id` (ou `engagement_id`) para não contar retentativa técnica como ação de marketing. `[doc oficial]`
3. O DWH **não** deve ser usado para rodar análise direta — a recomendação é carga incremental diária para o seu próprio DWH. Tabelas de fato têm retenção de **1080 dias**. `[doc oficial]`

---

## 6. Dicionário de fatos de comunicação

**`j_communication.fact_type_id`**
`1` CREATE · `2` SENT · `3` IMPRESSION · `4` CLICK · `5` FAIL · `6` DELIVERED · `7` OPTOUT · `8` READ · `9` DELETE · `10` SNOOZE `[doc oficial]`

**`dm_resource.resource_type_id`**
`1` Mail · `2` Popup · `3` SMS · `4` Push · `5` Inbox · `9` IVR `[doc oficial]`

**Joins úteis:** `resource_id → dm_resource` (`resource_subject` traz o corpo completo do SMS, incluindo o link) · `label_provider_id → dm_providers_sms` · `root_audience_id → dm_audience` · `fail_reason_id → dm_com_fail_reason`. `[doc oficial]`

**Motivos de falha vistos em produção:** `EXECUTION_TIMEOUT`, `CANNIBALISATION`, `INVALID_PHONE_NUMBER`. 🔴 O schema **não** registra qual campanha concorrente venceu o conflito de canibalização, nem as regras de prioridade/frequency cap. `[testado por mim]`

**Reconstruir tier/braço de teste quando não são colunas:** se os templates carregam a informação no nome (ex.: `Jornada de STD - <valor> - Giros`), dá para extrair tier e arm por parsing do nome do template referenciado em `j_communication`, com redundância cruzada em `j_bonuses` / `dm_bonus_template.internal_name`. `[testado por mim]`

---

## 7. Canais on-site

- **Pop-up** exige o usuário **em sessão**. Falha alta em canal on-site normalmente significa "usuário não estava no site" — não é bug de render. `[testado por mim]`
- **Inbox** é o canal de baixo atrito para apresentar missão/progresso a quem já está dentro. `[testado por mim]`
- Widget/banner/mission/tournament/mini-game são formatos on-site medidos por `entered/shown/viewed/click`; off-site por `sent/delivered/opened/answered/click`. `[suposição]` (PRD §3.1)
- 🔴 Correlação enganosa: "quem viu o pop-up depositou mais" está confundida por estar no site ser pré-condição das duas coisas. Corrigir o render **não** converte automaticamente quem falhou. `[testado por mim]`

---

## 8. RCS via Plugni — estado real da implementação

**Os 4 blocos necessários para disparar RCS:** (1) gateway ativo e vinculado à brand, (2) asset RCS completo, (3) campanha com activity RCS + `check user profile`, (4) preview antes do go-live. Falta um → não dispara, ou dispara errado. `[doc oficial]` + `[testado por mim]`

### Campos do asset RCS
| Campo | Regra | Origem |
|---|---|---|
| `Name` | Padrão buscável de produção. `Teste- Plugni` não vai para prod | `[testado por mim]` |
| `Status` | `Active` obrigatório — `Inactive` **não aparece** na campanha | `[testado por mim]` |
| `SMS fallback text` | Obrigatório na prática: aparelho sem RCS recebe isto. Precisa ter oferta + CTA sozinho. Suporta tags `{T}` | `[testado por mim]` |
| `RCS Message Type` | `MEDIA`, `TEXT`, `RICH CARD`, `CAROUSEL`, `TEMPLATE (SINGLE)` — a escolha muda os campos exigidos | `[testado por mim]` |
| `Media URL` | HTTPS público. Testar em aba anônima antes de salvar | `[testado por mim]` |
| `Suggested Actions` | Máx. 11 chips. CTA principal no chip 1 | `[testado por mim]` |
| `Content Variations` | Aba própria — variações para A/B com split de audiência | `[testado por mim]` |

### As duas rotas (ambas em aberto)
| | **Rota A — Template ID** | **Rota B — SMS estruturado** |
|---|---|---|
| Como | `TEMPLATE (SINGLE)` + Template ID gerado pela Plugni | Asset **SMS** com 5 linhas de valores puros; a Plugni parseia e monta o card do lado deles |
| Status | ⏳ ID nunca entregue pelo fornecedor | 🟡 Demonstrado pelo fornecedor, **nunca testado por nós** |
| Robustez | Contrato formal | 🔴 Frágil — linha fora de ordem entrega URL crua ao jogador |
| Métrica | RCS nativo | 🔴 Vira métrica de **SMS**; clique no botão provavelmente não volta à Smartico — rastreio só por UTM |

`[testado por mim]` no status; `[suposição]` na avaliação de métrica.

### Configuração do gateway Plugni
`Label → Gateways → Instant Messages → PlugniRCS → Authentication & Configuration`
- `API Base URL`: endpoint dedicado `https://api.plugni.com.br/v1/rcs/smartico/single` — 🟡 **não confirmado** se o campo leva o path completo ou só `/v1` (se der 404, testar só a base)
- `Bearer Token`: JWT fornecido pelo fornecedor
- `RCS Agent ID`: fornecido pelo gateway (valor omitido)

`[testado por mim]` nos valores; `[suposição]` no comportamento do campo `API Base URL`.

### Ponto de falha conhecido
🔴 O parser da Plugni **rejeita URL de imagem sem extensão real** (`.jpg`/`.png`). A URL gerada pela Smartico (`static5.smr.vc/...`) pode não terminar em extensão — nesse caso hospedar em CDN própria. `[testado por mim]` (relatado pelo fornecedor)

### 🔴 Pendência de segurança
O Bearer Token trafegou por WhatsApp e por chat, é um **JWT sem claim de expiração** e **não vence sozinho**. Precisa ser rotacionado manualmente. `[testado por mim]`

### Perguntas ainda abertas com a Plugni
1. O parse é por **ordem de linha** ou por rótulo?
2. Quebra de linha interna na copy quebra o parse?
3. Tags `{T}` de personalização no meio da linha quebram o parse?
4. Funciona no **Send Preview** ou só em disparo real?
5. `API Base URL` leva o path completo ou só `/v1`?
6. Trocar criativo reaproveita o template ou gera novo ID/homologação?

**Pré-requisito de base que ninguém checou:** RCS exige telefone válido + capability no device. Há falhas `INVALID_PHONE_NUMBER` isoladas e a taxa de fallback para SMS no BR é desconhecida — o fallback é asset de primeira classe, não resto. `[testado por mim]`

---

## 9. Arquiteturas de entrega de e-mail personalizado — o veredito registrado

| Arq. | Personalização acontece em | SendGrid | Esforço | Compliance |
|---|---|---|---|---|
| **A · Nativo** 🟢 | Liquid/HTML na Smartico + UI Widgets para listas | Gateway nativo | Baixo, sem dev | Nativo (opt-out, caps, tracking) |
| **B · Híbrido** 🟡 | Liquid/HTML na Smartico | Sua API → SendGrid (Custom Gateway) | Médio | Nativo no render, seu no transporte |
| **C · WebHook → agente** 🔴 | Seu serviço/LLM | Direto | Alto | **Por sua conta** — precisa reconstruir gate e tracking |

**Escolha registrada: A**, com o desenho de dois objetos descrito em `flow.md` §1 quando o conteúdo precisa vir de fora. `[doc oficial]` na descrição das capacidades; `[suposição]` na recomendação.

---

## 10. Pendências abertas de mensageria

| # | Item | Por que importa |
|---|---|---|
| 1 | Tags de `label` funcionam em Liquid email? | Define se T&C/links via label servem no canal |
| 2 | `{{event.*}}` renderiza HTML cru ou escapa? | Define se dá para injetar bloco HTML pelo bridge |
| 3 | Limite de tamanho dos campos do payload | Define se HTML monolítico é viável |
| 4 | Caps/limites de MAU para UI Widgets em e-mail | Define taxa de envio das listas |
| 5 | Reverse integration disponível no plano atual | Define se há tracking de volta para o DWH |
| 6 | Idempotência do `/events/v2` | Risco de disparo duplo |
| 7 | Personalização Liquid em SMS/WhatsApp/Push | Define o teto de personalização off-site |
| 8 | Em qual ambiente (ENV-2…ENV-7) a label está | Define endpoint/CNAME exato do branded link |
| 9 | DWH está contratado? (é serviço pago à parte) | Define se o tracking é auditável |
