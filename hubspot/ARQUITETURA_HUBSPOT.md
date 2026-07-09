# HubSpot → BigQuery: Arquitetura e Modelagem

**Cliente:** Benner (`mdass@bennerservicos.com.br`)
**Objetivo:** Trazer **deals** e **contacts** do HubSpot para o BigQuery e entregar uma **view final por origem e data**, no mesmo padrão que a agência já consome para o RD Station / Ads (`03_MKT_SALES.vw_ads_crm_results`).
**Stack:** no-code / low-code — **n8n** (extração) → **BigQuery** (staging → modelagem via SQL/Scheduled Queries). Sem servidor Python para manter.
**Conta:** portal HubSpot `50838441` · moeda **BRL** · TZ `America/Sao_Paulo` · ~89k contacts, ~16k deals.
**Status:** esquema **validado na conta real** via conector (jul/2026) e **testado ponta a ponta no BigQuery** com amostra (ver §6).
**Última atualização:** Julho 2026

---

## 1. Decisão de arquitetura (resumo)

Adotamos **ELT** (Extract-Load-Transform), não ETL:

```
HubSpot API (CRM v3)
   │  n8n: Schedule Trigger → HubSpot Search (incremental) → Google BigQuery (append)
   ▼
BigQuery — Camada RAW / Landing        (03_MKT_SALES.raw_hubspot_*)   ← append-only, 1 linha por versão
   │  Scheduled Query: MERGE (dedup por id, mantém última versão)
   ▼
BigQuery — Camada CLEAN / Staging      (03_MKT_SALES.Tb_HubSpot_*)    ← 1 linha por objeto (estado atual), tipado
   │  Views SQL
   ▼
BigQuery — Camada MODELAGEM (marts)    (03_MKT_SALES.vw_hubspot_*)    ← join deals↔contacts, unpivot de estágios
   │
   ▼
BigQuery — VIEW FINAL por origem+data  (vw_ads_crm_results estendida) ← agência consome aqui
```

**Por que assim:**

| Decisão | Motivo |
|---|---|
| **n8n só extrai e faz o load (raw)** | Mantém o low-code simples. Toda a lógica de negócio fica em SQL no BigQuery, onde a agência já modela (padrão `vw_*` existente). |
| **Camada RAW append-only + MERGE** | Resolve o problema clássico de **duplicação** ao rodar o schedule repetido (relatado pela comunidade n8n). O `MERGE` mantém só a versão mais recente por `id`. |
| **Sync incremental por `hs_lastmodifieddate`** | Após a carga inicial, cada execução puxa só o que mudou → reduz >90% das chamadas e respeita o rate limit. |
| **View final conforme o esquema de `vw_ads_crm_results`** | A agência **já consome** essa view. O HubSpot entra como mais uma fonte no `UNION` (coluna `source_table`), lado a lado com RD e Ads, comparável por **`origem` + `event_date`**. |

---

## 2. Recursos da API do HubSpot que vamos usar

Base URL: `https://api.hubapi.com` · Auth: **Private App token** no header `Authorization: Bearer <token>`.

> ⚠️ **Sobre a "API key":** as *API keys* legadas (`?hapikey=`) foram **descontinuadas** pelo HubSpot. O que hoje se gera em *Settings → Integrations → Private Apps* é um **access token de Private App**. Confirme que o token do cliente Benner é de Private App e tem os scopes de leitura: `crm.objects.contacts.read`, `crm.objects.deals.read`, `crm.schemas.deals.read`, `crm.schemas.contacts.read`.

### 2.1 Endpoints

| Uso | Endpoint | Observação |
|---|---|---|
| Listar contatos | `GET /crm/v3/objects/contacts` | `?limit=100&after=<cursor>&properties=...&associations=deals` |
| Listar deals | `GET /crm/v3/objects/deals` | `?limit=100&after=<cursor>&properties=...&associations=contacts` |
| **Busca incremental** | `POST /crm/v3/objects/{contacts\|deals}/search` | Filtro `hs_lastmodifieddate GTE <watermark>`, `sort` asc, `limit` até 200. **Cap de 10.000 resultados por query.** |
| Mapear estágios/pipelines | `GET /crm/v3/pipelines/deals` | Traduz `dealstage` (ID) → rótulo legível e ordem. |
| Descobrir propriedades reais | `GET /crm/v3/properties/{contacts\|deals}` | **Rodar 1x** para validar os nomes exatos na conta Benner (custom properties de UTM etc.). |

### 2.2 Paginação e limites

- **Paginação:** resposta traz `paging.next.after` → repassar em `after` até não vir mais. `limit` 100 (list) / 200 (search).
- **Cap do Search:** máximo **10.000 registros por query**. Para carga histórica, janelar por tempo (ex.: mês a mês) ou avançar o *watermark* para o `hs_lastmodifieddate` do último registro quando bater no teto.
- **Rate limit (Private App):** ~**190 chamadas / 10s** (Pro; até 250 com add-on). O Search tem limite adicional de poucas req/s. → n8n com *batching* e respeito a `429 Retry-After`.

### 2.3 Propriedades de ORIGEM e DATA (o coração do pedido)

**Contacts — origem:**

| Propriedade | Papel |
|---|---|
| `hs_analytics_source` | **Original Source** (enum) — a "origem" canônica |
| `hs_analytics_source_data_1` | Drill-down 1 (ex.: campanha / rede) |
| `hs_analytics_source_data_2` | Drill-down 2 (ex.: palavra-chave / conta) |
| `hs_latest_source`, `hs_latest_source_data_1/2` | Última origem (re-engajamento) |
| `hs_analytics_first_url`, `hs_analytics_last_url` | URL de 1ª/última visita |
| `first_conversion_event_name`, `recent_conversion_event_name` | 1ª/última conversão |

Valores do enum `hs_analytics_source`: `ORGANIC_SEARCH`, `PAID_SEARCH`, `EMAIL_MARKETING`, `SOCIAL_MEDIA`, `PAID_SOCIAL`, `REFERRALS`, `OTHER_CAMPAIGNS`, `DIRECT_TRAFFIC`, `OFFLINE`, `CRM_UI`, etc.

> ✅ **UTMs — validado:** a conta Benner **não tem** propriedades `utm_*` customizadas. A atribuição é 100% via `hs_analytics_source` (enum) + `source_data_1/2` (URL de origem, palavra-chave, `INTEGRATION`/`IMPORT`/`CRM_UI`). Por isso as colunas `UTM_*` do esquema padrão ficam `NULL` para o HubSpot; a dimensão de canal é a `origem`.
>
> Valores reais do enum `hs_analytics_source` na conta: `ORGANIC_SEARCH`, `PAID_SEARCH`, `PAID_SOCIAL`, `SOCIAL_MEDIA` (rótulo "Organic Social"), `EMAIL_MARKETING`, `REFERRALS`, `AI_REFERRALS`, `OTHER_CAMPAIGNS`, `DIRECT_TRAFFIC`, `OFFLINE`.

**Contacts — datas / funil:**

| Propriedade | Papel |
|---|---|
| `createdate` | Data de criação do contato (= "cadastro" / entrada no topo) |
| `lifecyclestage` | Estágio atual (subscriber/lead/mql/sql/opportunity/customer) |
| `hs_v2_date_entered_lead` | Entrou em Lead |
| `hs_v2_date_entered_marketingqualifiedlead` | Entrou em MQL |
| `hs_v2_date_entered_salesqualifiedlead` | Entrou em SQL |
| `hs_v2_date_entered_opportunity` | Entrou em Opportunity |
| `hs_v2_date_entered_customer` | Virou Cliente |
| `hs_lastmodifieddate` | *Watermark* do sync incremental |

> ✅ **Validado na conta Benner:** usa-se o modelo **v2** (`hs_v2_date_entered_<stage>`). O legado `hs_lifecyclestage_*_date` vem **vazio** nesta conta.

**Deals — origem, datas, valor:**

| Propriedade | Papel |
|---|---|
| `hs_analytics_source`, `hs_analytics_source_data_1/2` | Origem do deal (herdada do contato) |
| `dealname`, `dealstage`, `pipeline` | Nome, estágio, funil |
| `amount` | Valor |
| `createdate` | Criação do deal (→ `deals_created`) |
| `closedate` | Fechamento (→ base de `deals_won/lost`) |
| `hs_is_closed`, `hs_is_closed_won` | Flags de fechamento/ganho |
| `hs_lastmodifieddate` | *Watermark* |
| **associations → contacts** | Liga o deal ao contato (e-mail, origem do contato) |

---

## 3. Modelagem no BigQuery (dataset `03_MKT_SALES`)

Espelha o padrão do RD (`Tb_RDCRM_Deals` / `Tb_RDMKT_Contacts` → `vw_rdcrm_deals_stage` / `vw_rd_leads_stages`).

### Camada RAW (append-only) — escrita pelo n8n
- `raw_hubspot_deals` — colunas selecionadas + `_synced_at TIMESTAMP` + `_raw JSON` (payload bruto p/ resiliência a novas propriedades).
- `raw_hubspot_contacts` — idem.

### Camada CLEAN (estado atual) — Scheduled Query com MERGE
- `Tb_HubSpot_Deals` — 1 linha por `Deal_ID`, tipado, `origem` normalizada.
- `Tb_HubSpot_Contacts` — 1 linha por `Contact_ID`, tipado, `origem` normalizada.

### Camada MODELAGEM (views)
- `vw_hubspot_contacts_lifecycle` — 1 linha por contato (dedup), campos de origem + carimbos de estágio.
- `vw_hubspot_deals_stage` — deals + contato associado (join por associação/e-mail), como `vw_rdcrm_deals_stage`.
- `vw_hubspot_stage_events` — **unpivot** dos carimbos de data de estágio → fato `(origem, stage, event_date)`. É o que permite contar o funil **por data em que o estágio aconteceu** (não só a data de criação), igual à lógica do `vw_rd_tracking_stage_lifecycle`.
- `vw_hubspot_leads_stages` — agrega o funil **por `origem` + `event_date`**, no **esquema padronizado** de `vw_ads_crm_results` (mesmas colunas: `contacts, leads, lifecycle_stage_mql, lifecycle_stage_sql, opportunities, deals_created, deals_closed, deals_lost, deals_won, clients, amount, ...`).

### VIEW FINAL (consumo da agência)
`vw_ads_crm_results` recebe um 3º ramo no `UNION` lendo `vw_hubspot_leads_stages` (`source_table = 'hubspot'`). Assim a agência compara **Ads × RD × HubSpot** pela mesma **origem** e **data**, sem nova view para aprender. (SQL pronto em `sql/03_views.sql`.)

### De-para de ORIGEM (HubSpot → `origem` padronizada)

| `hs_analytics_source` | `origem` |
|---|---|
| `ORGANIC_SEARCH` | Busca Orgânica |
| `PAID_SEARCH` | Busca Paga |
| `PAID_SOCIAL` | Social Pago |
| `SOCIAL_MEDIA` | Social Orgânico |
| `EMAIL_MARKETING` | E-mail Marketing |
| `REFERRALS` | Referência |
| `OTHER_CAMPAIGNS` | Outras Campanhas |
| `DIRECT_TRAFFIC` | Tráfego Direto |
| `OFFLINE` | Offline |
| (demais / null) | Não informado |

> Ajustar os rótulos para **baterem exatamente** com os valores de `origem` que o RD já usa, para o `UNION` somar certo. Ver ação de validação em §5.

---

## 4. Blueprint do workflow n8n (extração incremental)

Um workflow por objeto (ou um com dois ramos). Nós:

1. **Schedule Trigger** — ex.: a cada 1h ou 1x/dia (03h, alinhado ao Meta Ads).
2. **BigQuery (read)** — lê o *watermark*: `SELECT MAX(hs_lastmodifieddate) FROM Tb_HubSpot_Deals`. (Alternativa: guardar em `_sync_state` ou no *static data* do n8n.)
3. **HubSpot** (ou HTTP Request no endpoint `/search`) — filtro `hs_lastmodifieddate GTE {{watermark}}`, `sort` asc, `properties` = lista do §2.3, `associations`. **Loop de paginação** com `after`.
4. **(opcional) Function/Set** — normaliza tipos e achata `properties`/`associations`.
5. **Google BigQuery (append)** — insere em `raw_hubspot_deals` / `raw_hubspot_contacts` com `_synced_at = now()`.
6. **BigQuery (Scheduled Query, fora do n8n)** — `MERGE` raw → `Tb_HubSpot_*` (dedup). Roda logo após, ou o n8n dispara via nó BigQuery *query*.

> **Anti-duplicação:** nunca "GET ALL" direto para a tabela final. Sempre **append no raw → MERGE**. A carga inicial (histórico) é feita uma vez janelando por período; depois só incremental.

Nós nativos existem: **HubSpot node** e **Google BigQuery node** no n8n (ver Fontes). O de HubSpot cobre get/create/update de contacts e deals; para o `/search` incremental com filtros finos, o **HTTP Request node** dá mais controle.

---

## 5. Validação na conta real (FEITA via conector, jul/2026)

| Item | Resultado |
|---|---|
| Propriedades de origem | `hs_analytics_source` (+ `source_data_1/2`) em contacts **e** deals ✓ |
| UTMs customizados | **Não existem** — atribuição só por `hs_analytics_source` |
| Datas de funil | Modelo **v2** (`hs_v2_date_entered_*`); legado vazio |
| Pipelines de deals | **Vários** (New Logo, Base, Canais, Arquiteto, Adm. Comercial, Sales Pipeline, Migração), cada um com stage IDs próprios |
| Ganho/Perdido | Usar **`hs_is_closed_won` / `hs_is_closed`** (booleanos, independem do pipeline) — não mapear por rótulo de stage |
| Origem dos deals | Quase sempre `OFFLINE` (IMPORT/CRM_UI) → herdar do **contato associado** |
| `amount` | Frequentemente vazio; moeda `deal_currency_code = BRL` |
| Volumes | ~89k contacts, ~16k deals → **carga inicial janelada** (cap 10k do Search) |

**Pendência única para produção:** puxar as **associações deal↔contact** no n8n (o Search do conector não as traz) para que a origem "de marketing" role do contato para o deal. Já está previsto no `vw_hubspot_deals_stage` via `COALESCE`.

## 6. Teste ponta a ponta no BigQuery (FEITO)

Carregada uma amostra real (16 contacts + 10 deals ganhos) em `raw_hubspot_*` → `MERGE` → `Tb_HubSpot_*` → views. A `vw_hubspot_leads_stages` retornou o funil por **origem + data** corretamente, ex.:

```
origem           data        contacts leads mql clients deals_won  valor_ganho(BRL)
Busca Orgânica   2026-07-08     2       2    -     -        -            -
Busca Paga       2026-07-08     3       3    -     -        -            -
Tráfego Direto   2026-07-08     2       1    -     -        -            -
Offline          2026-05..06    6       6    4     6        -            -
Offline          2026-07-07     -       -    -     -        5      1.550.632,89
Não informado    2026-07-07     -       -    -     -        5      1.282.228,73
```

> As tabelas `03_MKT_SALES.raw_hubspot_*`, `Tb_HubSpot_*` e as `vw_hubspot_*` **já existem** no BigQuery. Contêm só a amostra de teste — dá para `TRUNCATE TABLE` nos `raw_*`/`Tb_*` antes da primeira carga completa pelo n8n.

## 7. Próximo passo — endpoint no n8n

Ver o blueprint no §4. A criação do workflow n8n (Schedule → HTTP `/search` incremental com paginação → normalização → BigQuery append → Scheduled Query MERGE) é a próxima etapa.

---

## 8. Arquivos deste diretório

| Arquivo | Conteúdo |
|---|---|
| `ARQUITETURA_HUBSPOT.md` | Este documento |
| `sql/01_raw_and_clean_tables.sql` | DDL das tabelas RAW e CLEAN + template do MERGE |
| `sql/02_scheduled_merge.sql` | Scheduled Queries de MERGE (dedup) |
| `sql/03_views.sql` | Views de modelagem + `vw_hubspot_leads_stages` + patch do `UNION` na view final |
| `N8N_WORKFLOW.md` | Guia passo a passo dos workflows n8n (contacts e deals) |
| `n8n/hubspot_contacts_to_bigquery.json` | Workflow n8n importável — contacts |
| `n8n/hubspot_deals_to_bigquery.json` | Workflow n8n importável — deals (com associações) |

---

## Fontes

- [HubSpot — CRM Properties (guia)](https://developers.hubspot.com/docs/api-reference/crm-properties-v3/guide)
- [HubSpot — Contacts (guia da API)](https://developers.hubspot.com/docs/guides/api/crm/objects/contacts)
- [HubSpot — API usage guidelines and limits](https://developers.hubspot.com/docs/developer-tooling/platform/usage-guidelines)
- [HubSpot — Increasing our API limits (changelog)](https://developers.hubspot.com/changelog/increasing-our-api-limits)
- [HubSpot Community — 10.000 record limit no Search API](https://community.hubspot.com/t5/APIs-Integrations/Clarification-Required-on-10-000-Record-Limit-in-CRM-Search-API/td-p/1181810)
- [HubSpot — Stage calculated properties (datas de lifecycle)](https://knowledge.hubspot.com/properties/stage-calculated-properties)
- [HubSpot API: Complete Guide for Marketing Data Analysts (2026)](https://improvado.io/blog/hubspot-api)
- [n8n — HubSpot node](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.hubspot)
- [n8n — Google BigQuery node](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.googlebigquery/)
- [n8n Community — HubSpot to BigQuery (duplicação em Cron)](https://community.n8n.io/t/hubspot-to-bigquery/12623)
- [BigQuery — MERGE upsert + dedup (staging pattern)](https://oneuptime.com/blog/post/2026-02-17-how-to-deduplicate-streaming-data-in-bigquery-using-merge-and-window-functions/view)
