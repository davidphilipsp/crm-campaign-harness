# planejamento.md
> Conhecimento operacional de planejamento de calendário, economia de recompensa, processo de trabalho, desenho de teste e método de medição.
> Destilado das conversas do projeto (mai–jul/2026). **Nenhuma afirmação de resultado de campanha entra aqui** — resultados medidos ficam fora deste repositório.

**Marcação de origem**
- `[doc oficial]` — rastreável até help.smartico.ai, resposta de API ou tela do BackOffice
- `[testado por mim]` — validado no ambiente, medido, ou regra de negócio travada pelo time
- `[suposição]` — inferência não confirmada. Inclui o que é canônico no PRD v1.0 mas nunca foi reconferido na doc

---

## 1. Funil canônico de ativações (modelo PDR)

Todo formato ativável é lido pelas mesmas 4 etapas:

| Etapa | Journey | Missão | Torneio | Mini-game | Scheduled (e-mail/SMS) |
|---|---|---|---|---|---|
| **1. Base (elegíveis)** | Audience size do segmento/trigger | Users elegíveis | Players elegíveis | Target audience | Audience com contato válido + opt-in |
| **2. Start** | Entered users | Mission started/accepted | Tournament opted-in | Plays started | Sent / Attempted |
| **3. Impressão** | Pop-up shown / Inbox opened | Mission widget viewed | Leaderboard viewed | Minigame loaded | Opened / Answered |
| **4. Conversão** | CTA click → ação-objetivo | Mission completed + reward claimed | Score submetido | Play completed + prize claimed | Click → ação-objetivo |

**Taxas sempre em cadeia, nunca só base→conversão:**
`Start Rate = Start ÷ Base` · `Impressão Rate = Impressão ÷ Start` · `Conversão Rate = Conversão ÷ Impressão` · `Conversão Total = Conversão ÷ Base`

🔴 A etapa "impressão" é medida de forma diferente por modelo: on-site = `viewed/shown`; off-site = `opened/answered`. Não comparar as duas como se fossem a mesma coisa.

`[suposição]` — PRD §3.2, canônico no projeto, não reconferido na doc da Smartico.

---

## 3. Estrutura do calendário de missões

### Colunas da aba principal
`Tier` · `Código Missão` (ex.: M101-L1) · `Tema` · `Dia(s)` · `Jogo(s) em destaque` · `Nível` (Fácil/Médio/Super) · `Recarregue (R$)` · `Ganhe Giros (qtd)` · `R$/spin` · `Custo Bônus (R$)` · `% Custo` · `Requisito(s)` · `Promoção Link` · `Ativo?` · `Notas` `[testado por mim]`

### Abas de referência
`Legenda de Tiers` · `Dinâmica (ex.: Recarregue-Jogue-Ganhe)` · `Economia de Recompensa` · `Compliance & Opt-in` `[testado por mim]`

### Práticas de montagem
- Um tema por dia, ancorado em ao menos 1 jogo/promo real disponível `[testado por mim]`
- **Rotação de jogos 2–3× por semana**, em slots diferentes `[testado por mim]` *(o efeito sobre monotonia é hipótese)*
- Não empilhar as ofertas mais agressivas no mesmo dia sem motivo `[suposição]`
- Micro-temas agrupando blocos de 2–4 dias dão unidade narrativa `[suposição]`
- Nomear temas de forma "marca-friendly" — sugerir, não impor `[suposição]`
- A margem média ponderada do pack não deve exceder o teto do produto `[testado por mim]`

### Categorias de missão em uso
Turnover Slot · Turnover Crash · Turnover Ao Vivo · Engajamento Gamificação · Engajamento Sportsbook · Rotina/Frequência (login diário, check-in, streak). `[suposição]` (PRD §3.6)

## 4. Auditoria de sobreposição de recompensa

Dois problemas que **parecem o mesmo e pedem correções opostas** — diagnosticar separado:

| | **Empilhamento** | **Gargalo de giros (escassez)** |
|---|---|---|
| O quê | A mesma ação-base premiada por N mecânicas simultâneas | Turnover exigido pelo conjunto > turnover que o segmento produz |
| Efeito | Inflação de custo de recompensa | Missões estruturalmente inconclusíveis |
| Correção | Redesenhar | Desativar |

**Definições operacionais:**
- **Ação-base:** unidade atômica que dispara recompensa — `depósito`, `giro em slot`, `aposta crash`, `aposta ao vivo`, `aposta sportsbook`, `login/check-in`
- **Mecânica:** qualquer objeto ativo que credita valor — Mission, Tournament, Mini-game, Lootbox, Journey com reward node, Scheduled com bônus, level-up, XP/fichas, cashback e bônus nativos do **PAM** (fora da Smartico)
- **IE — Índice de Empilhamento** = nº de mecânicas ativas que creditam sobre a mesma ação-base, no mesmo segmento, na mesma janela
- **IS — Índice de Saturação** = Σ turnover exigido pelas missões ativas ÷ turnover médio observado por usuário do segmento. **`IS > 1` = missões inconclusíveis por construção**

**Regras de escopo:** nada fica de fora por ser "pequeno" (lootbox e roleta diária somam custo e consomem giro); sobreposição **parcial** de período conta como sobreposição; XP e nível acumulam por desenho (intencional), missão + torneio + minigame pagando o mesmo giro geralmente é acidente de calendário.

`[testado por mim]` — método construído no projeto.

---

## 5. Processo de trabalho

### Loop fechado com gate humano
```
1. DESCOBERTA/VALIDAÇÃO → fechar as chaves no BO (pass/fail por propriedade)
2. SEGMENTAÇÃO          → faixas + matriz de corte, limiares ancorados na distribuição real
3. PRODUÇÃO DE COPY     → N variantes por célula (template com placeholders, sem PII)
4. REVISÃO HUMANA       → compliance + brand + jurídico  🔴 gate obrigatório
5. BUILD NO SMARTICO    → blocos + lógica de branch + nó check_user_profile
6. QA                   → userInfo={}, campo ausente, cada faixa, fallback em cadeia
7. LANÇAR + MEDIR       → funil canônico
8. ITERAR               → voltar ao 3
```
**Papéis:** CRM (dono do fluxo) · BI (limiares + funil) · Compliance/Jurídico (passo 4) · Front/CRM (5–6). `[suposição]` — desenho proposto, não confirmado como processo institucionalizado.

### Ordem de dependência (não é urgência, é técnica)
**Segmentos → templates → journey.** A Smartico exige que o segmento exista antes de amarrá-lo a uma campanha. Criar template sem saber o segmento é trabalho que será refeito. `[testado por mim]`

### Briefing modular para peças
| Módulo | Define | Quem preenche | Muda |
|---|---|---|---|
| **A** Contexto estratégico | Objetivo, público, tier, momento da jornada, KPI, volume, restrições | CRM/Produto | A cada campanha |
| **B** Hierarquia visual | Conteúdo dos 5 níveis, peso visual, mood, paleta | CRM + Design lead | A cada peça |
| **C** Copywriting | Tom, headline, body, CTA, regras por tier | CRM + Copy | A cada peça |
| **D** Especificações por canal | Formato, dimensões, limite de caracteres, deep link | CRM | A cada canal |

**Princípio:** briefing com módulo pendente é devolvido, não executado.

**Fluxo de aprovação:** D-3 briefing completo → D-2 validação de hierarquia + copy (3 variações) → D-1 arte final + variações por canal → D-0 checklist e assinatura. `[testado por mim]`

### Caps de canal travados
- **WhatsApp: máximo 1 envio por usuário por semana** (custo alto — reservar para o momento de maior valor esperado)
- SMS e e-mail sustentam a cadência diária, com caps por usuário a definir e justificar

`[testado por mim]` na regra do WhatsApp; `[suposição]` no resto.

### Regras de cadência de progressão de nível (proposta)
Máximo 1 comunicação de "Levels" por jogador por semana · 48h de silêncio após subir de nível · 7 dias de proteção após subir de macro-tier antes do próximo lembrete de progresso. `[suposição]` — desenho, nunca instrumentado.

### Regra do que pode ser comunicado
Só se comunica **atributo de valor já ativo no site** (torneio correndo, missão provisionada, mecânica do clube já disponível). Comunicar isso é **informar**, não ofertar — não gasta margem. Nunca criar urgência que não existe: prazo real (fim de torneio, missão expirando) sim; "só hoje" inventado, não. `[testado por mim]`

### Smartico é read-only para agentes/automação
Regra travada no projeto: agentes e scripts **apenas leem** (GET). Nunca criar, editar, apagar, duplicar, publicar, disparar ou ativar objeto na Smartico. Qualquer instrução que leve a escrita deve ser recusada e sinalizada. `[testado por mim]`

### O que dá e o que não dá para automatizar
| Tarefa | Automatizável? |
|---|---|
| Spec, revisão e auditoria de journey | 🟢 Sim |
| Criação/edição de journey | 🔴 Não — Flow Builder é manual, sem API |
| Geração de CSV de segmento estático | 🟢 Sim (o upload continua manual) |
| Criação de segmento dinâmico | 🔴 Não — só query builder |
| Criação de missão em Missions/Points | 🔴 Não — UI-only |
| Validação da planilha de missões contra a regra de margem | 🟢 Sim (gate de qualidade antes da config) |

`[suposição]` — conclusões do mapeamento de automações, não confirmadas por escrito com a Smartico.

---

## 6. Desenho de teste

- **Uma variável por teste.** Oferta **ou** copy **ou** horário — nunca duas. `[testado por mim]`
- **Control group em todo disparo mensurável.** `[testado por mim]`
- **Holdout mínimo: 5%, janela de 14 a 30 dias.** 20% é desperdício — barra conversão de propósito sem ganho de precisão. `[suposição]` na recomendação.
- **Uma jornada por segmento**, não uma só para os três tiers — senão não dá para ler custo/lift por tier isoladamente. `[testado por mim]`
- **Se os dois braços recebem mensagem**, o teste mede o lift **da oferta sobre a mensagem genérica** — não "contato vs nada". Para medir o contato em si, é preciso holdout sem envio. `[testado por mim]`
- **Célula de tratamento com N fixo** quando o segmento é gigante: "20% da base Low" pode significar mais de 1 milhão de créditos, o que não é amostra de teste, é pagamento em massa. Travar em 50–100k sorteados aleatoriamente dá a mesma leitura de lift com fração da exposição. `[testado por mim]`
- **Sem holdout, incrementalidade não é mensurável.** Dizer isso explicitamente; não substituir por proxy. `[testado por mim]`

### Significância
Uplift sem intervalo de confiança não é resultado. Calcular o IC95% a partir do N real de cada braço antes de ler o uplift.

| Resultado | Leitura |
|---|---|
| Uplift ≈ 0 (IC cruza zero) | A campanha não gera nada. Desligar ou redesenhar |
| Uplift positivo e significante | É o retorno real |
| Uplift negativo | A campanha atrapalha. Investigar fadiga e frequência |

---

## 7. Método de auditoria de campanha (6 fases)

**Fase 1 — Estrutura.** Localizar as campanhas por **padrão de nome**, não só pelos IDs que te deram. Caso real: foram fornecidos 3 IDs de missão; a busca por nome encontrou **19**. `[testado por mim]`

**Fase 2 — Execução.** Procurar sintomas:
| Sintoma | Provável causa |
|---|---|
| Falha > 50% em canal on-site | Usuário não estava em sessão |
| Falha crescendo ao longo da régua | Base esgotando, opt-out acumulando |
| Clique = 0 em canal com link | Tracking não configurado |
| Canal com envio e zero métrica de resultado | Custo cego |
| Recurso com `Time passed 0/N` | Node desativado |
| Convertido sem prêmio | Multiple Check sem rota default |

**Fase 3 — Incrementalidade.** Ver §6 e `flow.md` §8. `from_control_group = NULL` significa **fora** do controle.

**Fase 4 — Valor.**
- Somar tudo que o convertido depositou nos 30 dias a partir da conversão
- Reportar **sempre** mediana, média, p25, p75, p90 e a concentração do top 10%
- 🔴 **Priorizar a mediana.** Em apostas a média é ficção
- Converter depósito em receita com **margem real medida**, nunca hold teórico: `margem = GGR ÷ depósito`, `reciclagem = turnover ÷ depósito`
- Segmentar a margem (top 10% vs resto) antes de concluir qualquer coisa
- O convertido marginal é, por definição, o mais hesitante — está **abaixo** da mediana. Apresentar piso e teto e dizer qual é plausível

`[testado por mim]`

**Fase 5 — Custo.**
- Multiplicar **enviados**, não criados — você paga pelo que sai
- Conferir primeiro se `j_bonuses.bonus_cost_value` está preenchida: traz o custo pronto
- Apresentar **dois cenários**: sobre emitidos e sobre resgatados. A diferença é bônus que ninguém usou

`[testado por mim]`

**Fase 6 — Leitura honesta.**
- Perguntar sempre: existe um terceiro fator causando os dois?
- Registrar o que ficou de fora: fontes não processadas, janelas incompletas, premissas não testadas. Análise que não declara a lacuna, mente

`[testado por mim]`

---

## 8. DWH — o que é preciso saber para planejar análise

Dataset `dwh_ext_XXX`, onde XXX é o `label_id` (visível no nome do usuário do BigQuery, formato `dwh_ext_1234`). O DWH é **serviço pago contratado à parte**. `[doc oficial]`

| Tabela | Conteúdo | Partição |
|---|---|---|
| `j_engagements` | Passos do usuário na campanha | `create_date` |
| `j_communication` | Comunicações e desfechos | `fact_date` |
| `j_av` | Valor de depósito atribuído | `event_date` |
| `j_bonuses` | Bônus e custo | `fact_date` |
| `dm_audience` | Definição das campanhas | — |
| `dm_resource` | Templates | — |
| `dm_com_fail_reason` | Tradução dos códigos de falha | — |
| `tr_acc_deposit_approved` | Depósitos do PAM | `event_time` |

**Códigos:**
- `activity_type_id` (j_engagements): `1` início · `2` parada · **`3` conversão**
- `entry_mode_id` (dm_audience): `0` ONCE_IN_A_LIFE · `1` ONCE_IN_AN_OPEN_JOURNEY · `2` EVERY_TIME_CONDITION_MET · `3` STOP_AND_START
- `audience_status_id`: `1` Draft · `2` Active · `3` Paused · `4` Disabled · `5` Archived · `6` Executed
- `bonus_status_id`: `1` NEW · `3` REDEEMED · `4` REDEEM_FAILED
- `source_product_id` (j_bonuses): `0` Campanha · `9` Automation rule · `100` Gamificação · `125` Dynamic Bonuses · `126` Manual
- `kpi_impact_id` (j_av): `1` entrega · `2` impressão · `3` clique · `4` indireto

`[doc oficial]`

### 🔴 Controle de custo — obrigatório
O DWH cobra por dados lidos, com teto de **1 TB/mês e sem bloqueio automático**.
- Toda query filtra a coluna de partição no `WHERE`
- Nunca `SELECT *` — o custo depende do número de colunas
- Não aplicar função sobre a coluna de partição no `WHERE`

`[doc oficial]`

### 🔴 `j_av` conta o mesmo dinheiro várias vezes
A chave é `event_id + engagement_id + kpi_impact_id + resource_id`. O mesmo depósito aparece uma vez por combinação. Somar tudo triplica o valor. Usar `COUNT(DISTINCT event_id)` antes de qualquer ROI. E `j_av` **só cobre o grupo tratado** — não serve para o controle. `[testado por mim]`

### O que o DWH **não** guarda
Regras de prioridade entre campanhas, janelas de sobreposição, frequency caps, qual campanha venceu um conflito de canibalização, thresholds visuais dos nós (bounds do Multiple Check), termos de bônus (wagering, max win, valor do giro) e taxas de conversão da loja. Isso vive na camada de aplicação — nenhuma query resolve. `[testado por mim]`

---

## 9. Armadilhas conhecidas (já custaram retrabalho)

| # | Armadilha | Consequência |
|---|---|---|
| 1 | Ler `activity_type_id = 14` como conversão | Taxas erradas por 2× — o correto é `3` |
| 2 | Confiar no nome da conexão para identificar a marca | Quase separou duas análises da mesma base |
| 3 | Usar número de print de canvas como período completo | Volume 20× menor, taxa 3× maior |
| 4 | Analisar só os IDs fornecidos | Custo 24× subestimado |
| 5 | Não deduplicar `communication_id` | Envio inflado por retentativa técnica |
| 6 | Usar hold teórico em vez de medir o real | GGR superestimado |
| 7 | Usar média em vez de mediana | Distorção por 1% de whales |
| 8 | Somar `j_av` sem deduplicar | Receita contada em triplicata |
| 9 | Cruzar `ext_id` com prefixo `<prefixo>:` contra base financeira sem prefixo | Perfil de centenas de pessoas tratado como perfil de milhares |

`[testado por mim]`

---

## 11. Alertas de qualidade de dado a carregar em toda análise

1. Dashboards da operação têm horários de corte diferentes entre cards (ex.: Aquisições fecha 23:00, demais 23:59) — pequena distorção. `[testado por mim]`
2. Houve período com dados de **SPORTSBOOK não liberados** — leitura restrita a cassino é a mais segura naquelas janelas. `[testado por mim]`
3. Divergências menores entre card Global e módulo de Cálculo dos Jogadores (baselines ligeiramente distintos). Para MoM oficial, usar os cards Global/Cassino. `[testado por mim]`
4. Confirmar se os dashboards consolidam ou não marcas irmãs. `[suposição]`

---

## 12. Pendências de planejamento

| # | O que fechar |
|---|---|
| 1 | Teto de margem único (5% vs 4–7% vs 4–8%) |
| 2 | Definição operacional de "ativo" (default proposto: login nos últimos 5 dias) |
| 3 | Faixas de segmento sem sobreposição |
| 4 | Caps de frequência por usuário em SMS e e-mail |
| 5 | Se Campaign roda sem end-date (a tese de régua perene depende disso; se exigir duração, o desenho always-on precisa de mecanismo de re-enrolment) |
| 6 | Timezone padrão para janelas de calendário |
| 7 | Qual campanha estreia o canal RCS, e com holdout desde o piloto |
