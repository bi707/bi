-- =====================================================================
-- HubSpot -> BigQuery | Camada RAW (landing) e CLEAN (estado atual)
-- Dataset: analytics-contas.03_MKT_SALES
-- Conta Benner (portal 50838441) | moeda BRL | TZ America/Sao_Paulo
--
-- Validado contra a conta real via conector HubSpot (jul/2026):
--   - Origem = hs_analytics_source ("Original Traffic Source")
--   - Datas de funil = modelo NOVO hs_v2_date_entered_<stage>
--     (o legado hs_lifecyclestage_*_date vem VAZIO nesta conta)
--   - Ganho/Perdido = hs_is_closed_won / hs_is_closed (varios pipelines,
--     stage IDs distintos por pipeline -> nao dá para mapear por rotulo)
--   - NAO existem propriedades utm_* customizadas
--   - Volumes: ~89k contacts, ~16k deals -> carga inicial JANELADA
--
-- Fluxo: n8n faz APPEND em raw_hubspot_* -> Scheduled Query MERGE em Tb_HubSpot_*
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) RAW / LANDING  (append-only; 1 linha por versão sincronizada)
--    O n8n escreve aqui. _raw guarda o objeto inteiro (resiliência a
--    novas propriedades); colunas-chave achatadas facilitam o MERGE.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `analytics-contas.03_MKT_SALES.raw_hubspot_deals` (
  Deal_ID              STRING,
  hs_lastmodifieddate  TIMESTAMP,
  _synced_at           TIMESTAMP,
  _raw                 JSON
)
PARTITION BY DATE(_synced_at)
CLUSTER BY Deal_ID;

CREATE TABLE IF NOT EXISTS `analytics-contas.03_MKT_SALES.raw_hubspot_contacts` (
  Contact_ID           STRING,
  hs_lastmodifieddate  TIMESTAMP,
  _synced_at           TIMESTAMP,
  _raw                 JSON
)
PARTITION BY DATE(_synced_at)
CLUSTER BY Contact_ID;


-- ---------------------------------------------------------------------
-- 2) CLEAN / STAGING  (1 linha por objeto = estado atual, tipado)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `analytics-contas.03_MKT_SALES.Tb_HubSpot_Deals` (
  Deal_ID              STRING,
  Deal_Name            STRING,
  Pipeline_ID          STRING,     -- id do pipeline (resolver rotulo via dim, ver 04)
  Pipeline_Stage_ID    STRING,     -- id do stage (varia por pipeline)
  Deal_Status          STRING,     -- open / won / lost (de hs_is_closed*)
  Deal_Win             BOOL,
  Deal_Amount          NUMERIC,    -- em BRL (deal_currency_code)
  Deal_Currency        STRING,
  Deal_Created_Date    TIMESTAMP,
  Deal_Closed_Date     TIMESTAMP,  -- so é fechamento real quando Deal_Status<>'open'
  Deal_Source_Raw      STRING,     -- hs_analytics_source (enum cru; quase sempre OFFLINE)
  Deal_Source          STRING,     -- origem normalizada (de-para)
  Deal_Source_Data_1   STRING,
  Deal_Source_Data_2   STRING,
  Contact_ID           STRING,     -- contato associado (principal) -> origem "de marketing"
  hs_lastmodifieddate  TIMESTAMP,
  _synced_at           TIMESTAMP
)
CLUSTER BY Deal_ID;

CREATE TABLE IF NOT EXISTS `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts` (
  Contact_ID               STRING,
  Contact_Name             STRING,
  Contact_Email            STRING,
  Contact_Lifecycle_Stage  STRING,
  Contact_Created_At       TIMESTAMP,
  Origem_Raw               STRING,   -- hs_analytics_source (enum cru)
  Origem                   STRING,   -- normalizada (de-para)
  Origem_Data_1            STRING,   -- hs_analytics_source_data_1 (URL / INTEGRATION / keyword)
  Origem_Data_2            STRING,   -- hs_analytics_source_data_2 (ex.: GOOGLE, id)
  Latest_Source            STRING,   -- hs_latest_source
  First_Conversion         STRING,   -- first_conversion_event_name (formulário)
  First_Touch_Campaign     STRING,   -- hs_analytics_first_touch_converting_campaign
  -- Carimbos de data de estágio (modelo v2) ---------------------------
  Became_Subscriber_Date   TIMESTAMP, -- hs_v2_date_entered_subscriber
  Became_Lead_Date         TIMESTAMP, -- hs_v2_date_entered_lead
  Became_MQL_Date          TIMESTAMP, -- hs_v2_date_entered_marketingqualifiedlead
  Became_SQL_Date          TIMESTAMP, -- hs_v2_date_entered_salesqualifiedlead
  Became_Opportunity_Date  TIMESTAMP, -- hs_v2_date_entered_opportunity
  Became_Customer_Date     TIMESTAMP, -- hs_v2_date_entered_customer
  hs_lastmodifieddate      TIMESTAMP,
  _synced_at               TIMESTAMP
)
CLUSTER BY Contact_ID;


-- ---------------------------------------------------------------------
-- 3) Controle de sync (watermark) — opcional
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `analytics-contas.03_MKT_SALES._hubspot_sync_state` (
  object_type   STRING,      -- 'deals' | 'contacts'
  watermark     TIMESTAMP,   -- último hs_lastmodifieddate processado
  updated_at    TIMESTAMP
);
