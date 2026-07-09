# n8n | HubSpot → BigQuery (extração incremental raw)

Guia passo a passo dos dois workflows (contacts e deals). Os JSON importáveis
estão em `hubspot/n8n/`. Depois de importar, ajuste as credenciais e revise as
versões dos nós (n8n muda `typeVersion` entre releases).

**Arquitetura:** cada workflow puxa só o que mudou desde o último sync
(`hs_lastmodifieddate`), grava o payload bruto em `raw_hubspot_*` (append) e um
MERGE consolida em `Tb_HubSpot_*`. Ver `ARQUITETURA_HUBSPOT.md`.

---

## 0. Credenciais no n8n (uma vez)

### 0.1 HubSpot — Private App token
- **HubSpot → Settings → Integrations → Private Apps → Create** com scopes de
  leitura: `crm.objects.contacts.read`, `crm.objects.deals.read`,
  `crm.schemas.contacts.read`, `crm.schemas.deals.read`, `crm.objects.owners.read`.
- Copie o **Access token** (`pat-na1-...`).
- No n8n: **Credentials → New → HubSpot App Token** (ou use um genérico
  **Header Auth**: header `Authorization`, valor `Bearer pat-na1-...`).
  Nos nós HTTP abaixo uso **Header Auth** para ter controle total.

### 0.2 Google BigQuery — Service Account
- Reusar a Service Account que já grava no BigQuery (a mesma do `credentials.json`).
- Garanta os papéis no projeto `analytics-contas`: **BigQuery Data Editor** (gravar em `03_MKT_SALES`) e **BigQuery Job User** (rodar queries).
- No n8n: **Credentials → New → Google BigQuery (Service Account)** → cole o JSON da service account.

---

## 1. Workflow A — Contacts

Nós, na ordem:

### 1.1 Schedule Trigger
- Ex.: **Every hour** (ou diário 03:00 America/Sao_Paulo, alinhado ao Meta Ads).

### 1.2 BigQuery — "Get watermark" (operation: *Execute Query*)
```sql
SELECT CAST(UNIX_MILLIS(COALESCE(MAX(hs_lastmodifieddate), TIMESTAMP '2015-01-01')) AS STRING) AS wm
FROM `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts`
```
Retorna `wm` = maior `hs_lastmodifieddate` já carregado, em **epoch millis**.

### 1.3 HTTP Request — "HubSpot Search Contacts"
- **Method:** POST
- **URL:** `https://api.hubapi.com/crm/v3/objects/contacts/search`
- **Authentication:** Header Auth (Bearer token do 0.1)
- **Body (JSON):**
```json
{
  "filterGroups": [{"filters": [
    {"propertyName": "hs_lastmodifieddate", "operator": "GTE", "value": "{{ $json.wm }}"}
  ]}],
  "sorts": [{"propertyName": "hs_lastmodifieddate", "direction": "ASCENDING"}],
  "properties": [
    "firstname","lastname","email","lifecyclestage","createdate","hs_lastmodifieddate",
    "hs_analytics_source","hs_analytics_source_data_1","hs_analytics_source_data_2",
    "hs_latest_source","first_conversion_event_name","hs_analytics_first_touch_converting_campaign",
    "hs_v2_date_entered_subscriber","hs_v2_date_entered_lead","hs_v2_date_entered_marketingqualifiedlead",
    "hs_v2_date_entered_salesqualifiedlead","hs_v2_date_entered_opportunity","hs_v2_date_entered_customer"
  ],
  "limit": 100,
  "after": "0"
}
```
- **Options → Pagination:**
  - Mode: *Update a Parameter In Each Request*
  - Parameter: **Body** → name `after` → value `={{ $response.body.paging?.next?.after }}`
  - **Stop when:** expression `={{ $response.body.paging?.next?.after ? false : true }}` (para quando não houver `paging.next`)
  - Isso pagina em blocos de 100 até esgotar (ou até o teto de 10.000 do Search — ver §3, backfill).
- **Options:** ligar *Split Into Items* pelo caminho `results` (ou use um nó **Item Lists → Split Out** em `{{$json.results}}`).

### 1.4 Code — "Build raw rows" (JavaScript, run once per item)
```js
const it = $json; // cada contato de results
return {
  json: {
    Contact_ID: it.id,
    hs_lastmodifieddate: it.properties?.hs_lastmodifieddate ?? null,
    _synced_at: new Date().toISOString(),
    _raw: JSON.stringify({ properties: it.properties })
  }
};
```

### 1.5 BigQuery — "Append raw_contacts" (operation: *Insert*)
- Project `analytics-contas` · Dataset `03_MKT_SALES` · Table `raw_hubspot_contacts`
- **Map** as colunas: `Contact_ID`, `hs_lastmodifieddate`, `_synced_at`, `_raw`.
- Obs.: se a inserção reclamar do tipo `JSON` em `_raw`, veja §4 (fallback STRING).

### 1.6 BigQuery — "MERGE contacts" (operation: *Execute Query*)
Cole o `MERGE` de **CONTACTS** de `sql/02_scheduled_merge.sql`. Roda 1x ao fim do batch.

---

## 2. Workflow B — Deals (com associação ao contato)

Igual ao A, mas com um passo a mais para trazer o contato associado (o `/search`
não retorna associações).

### 2.1 Schedule Trigger — idem 1.1

### 2.2 BigQuery — "Get watermark"
```sql
SELECT CAST(UNIX_MILLIS(COALESCE(MAX(hs_lastmodifieddate), TIMESTAMP '2015-01-01')) AS STRING) AS wm
FROM `analytics-contas.03_MKT_SALES.Tb_HubSpot_Deals`
```

### 2.3 HTTP Request — "HubSpot Search Deals"
- POST `https://api.hubapi.com/crm/v3/objects/deals/search`, Header Auth, paginação igual 1.3.
- **properties:**
```json
["dealname","pipeline","dealstage","amount","deal_currency_code",
 "createdate","closedate","hs_lastmodifieddate","hs_is_closed","hs_is_closed_won",
 "hs_analytics_source","hs_analytics_source_data_1","hs_analytics_source_data_2"]
```
- filtro/sort iguais (por `hs_lastmodifieddate` GTE `{{ $json.wm }}`, ASC).

### 2.4 HTTP Request — "Associations deals→contacts" (batch v4)
- POST `https://api.hubapi.com/crm/v4/associations/deals/contacts/batch/read`, Header Auth.
- **Body:** os IDs da página atual:
```json
{ "inputs": {{ $json.results.map(d => ({ id: d.id })) }} }
```
- Retorna, por deal, os contatos associados em `results[].from.id` / `results[].to[].toObjectId`.

### 2.5 Code — "Build raw deal rows"
```js
// junta cada deal com o 1º contato associado e monta o _raw no formato do MERGE
const deals = $item(0).$node["HubSpot Search Deals"].json.results || [];
const assoc = $json.results || []; // do nó de associações
const map = {};
for (const a of assoc) {
  const from = a.from?.id;
  const to = (a.to || [])[0]?.toObjectId;
  if (from) map[from] = to || null;
}
return deals.map(d => ({
  json: {
    Deal_ID: d.id,
    hs_lastmodifieddate: d.properties?.hs_lastmodifieddate ?? null,
    _synced_at: new Date().toISOString(),
    _raw: JSON.stringify({
      properties: d.properties,
      associations: { contacts: { results: map[d.id] ? [{ id: String(map[d.id]) }] : [] } }
    })
  }
}));
```

### 2.6 BigQuery — "Append raw_deals" (Insert em `raw_hubspot_deals`)
Colunas `Deal_ID`, `hs_lastmodifieddate`, `_synced_at`, `_raw`.

### 2.7 BigQuery — "MERGE deals" (Execute Query)
Cole o `MERGE` de **DEALS** de `sql/02_scheduled_merge.sql`.

---

## 3. Carga inicial (backfill) — teto de 10.000 do Search

O Search corta em 10.000 registros por query. Como filtramos por
`hs_lastmodifieddate GTE watermark` e ordenamos **ASC**, basta **rodar o workflow
várias vezes**: cada execução consome ~10k (dos mais antigos ainda não trazidos),
o `MERGE` avança o `MAX(hs_lastmodifieddate)`, e a próxima execução continua dali.

- **Contacts (~89k):** ~9 execuções até "zerar" o backlog; depois vira incremental.
- **Deals (~16k):** ~2 execuções.
- Dispare manualmente em sequência (ou deixe o Schedule rodar de hora em hora).
  O `MERGE` deduplica por id, então re-puxar a "borda" (GTE) não gera duplicata.

> Alternativa de backfill mais controlada: janelar por `createdate` (mês a mês)
> em vez de `hs_lastmodifieddate`. Não é necessário aqui.

---

## 4. Notas de robustez

- **Rate limit HubSpot:** ~190 req/10s (Pro). Com `limit=100` e paginação sequencial
  fica folgado. Trate `429` no nó HTTP (Options → *Retry On Fail*, com espera).
- **`_raw` JSON vs STRING:** se o nó BigQuery falhar ao inserir `_raw` como `JSON`,
  troque a coluna para `STRING` no `01_raw_and_clean_tables.sql` e, no `02`,
  envolva as leituras com `PARSE_JSON(_raw)` (ex.: `JSON_VALUE(PARSE_JSON(_raw), '$.properties.email')`).
- **Idempotência:** raw é append-only; o estado atual vem sempre do `MERGE`
  (dedup por id, mantém `hs_lastmodifieddate` mais recente). Reexecutar é seguro.
- **Um só workflow:** dá para juntar A e B com dois ramos após o Schedule; mantive
  separados para clareza e para agendar/ligar cada objeto de forma independente.

---

## 5. Depois do raw: modelagem

As views (`sql/03_views.sql`) já leem `Tb_HubSpot_*`. Rode-as uma vez (ou via
Scheduled Query) e a agência consome `vw_hubspot_leads_stages` — ou o
`vw_ads_crm_results` estendido — por **origem + data**.
