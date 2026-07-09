-- =====================================================================
-- HubSpot → BigQuery | Camada RAW (landing) e CLEAN (estado atual)
-- Dataset: analytics-contas.03_MKT_SALES
-- Padrão espelhado do RD: Tb_RDCRM_Deals / Tb_RDMKT_Contacts
--
-- Fluxo: n8n faz APPEND em raw_hubspot_* → Scheduled Query MERGE em Tb_HubSpot_*
-- Os nomes de propriedades devem ser confirmados via GET /crm/v3/properties/*
-- na conta Benner (ver §5 do ARQUITETURA_HUBSPOT.md).
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) RAW / LANDING  (append-only; 1 linha por versão sincronizada)
--    O n8n escreve aqui. Guardamos _raw (JSON) para não quebrar quando
--    novas propriedades surgirem, e colunas achatadas do que usamos hoje.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `analytics-contas.03_MKT_SALES.raw_hubspot_deals` (
  Deal_ID                STRING,
  hs_lastmodifieddate    TIMESTAMP,
  _synced_at             TIMESTAMP,   -- carimbo do n8n (now na extração)
  _raw                   JSON         -- payload bruto do objeto
)
PARTITION BY DATE(_synced_at)
CLUSTER BY Deal_ID;

CREATE TABLE IF NOT EXISTS `analytics-contas.03_MKT_SALES.raw_hubspot_contacts` (
  Contact_ID             STRING,
  hs_lastmodifieddate    TIMESTAMP,
  _synced_at             TIMESTAMP,
  _raw                   JSON
)
PARTITION BY DATE(_synced_at)
CLUSTER BY Contact_ID;


-- ---------------------------------------------------------------------
-- 2) CLEAN / STAGING  (1 linha por objeto = estado atual, tipado)
--    Colunas alinhadas ao esquema do RD para facilitar as views.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `analytics-contas.03_MKT_SALES.Tb_HubSpot_Deals` (
  Deal_ID                STRING,
  Deal_Name              STRING,
  Pipeline               STRING,
  Pipeline_Stage_ID      STRING,
  Deal_Stage             STRING,     -- rótulo (resolvido via /pipelines/deals)
  Deal_Status            STRING,     -- open / won / lost
  Deal_Win               BOOL,
  Deal_Amount            NUMERIC,
  Deal_Created_Date      TIMESTAMP,
  Deal_Closed_Date       TIMESTAMP,
  Deal_Source_Raw        STRING,     -- hs_analytics_source (enum cru)
  Deal_Source            STRING,     -- origem normalizada (de-para)
  Deal_Source_Data_1     STRING,
  Deal_Source_Data_2     STRING,
  Contact_ID             STRING,     -- contato associado (principal)
  Contact_Email          STRING,
  hs_lastmodifieddate    TIMESTAMP,
  _synced_at             TIMESTAMP
)
CLUSTER BY Deal_ID;

CREATE TABLE IF NOT EXISTS `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts` (
  Contact_ID                      STRING,
  Contact_Name                    STRING,
  Contact_Email                   STRING,
  Contact_Lifecycle_Stage         STRING,
  Contact_Created_At              TIMESTAMP,
  Origem_Raw                      STRING,   -- hs_analytics_source (enum cru)
  Origem                          STRING,   -- normalizada (de-para)
  Origem_Data_1                   STRING,   -- hs_analytics_source_data_1
  Origem_Data_2                   STRING,   -- hs_analytics_source_data_2
  Latest_Source                   STRING,   -- hs_latest_source
  First_Conversion                STRING,   -- first_conversion_event_name
  Last_Conversion                 STRING,   -- recent_conversion_event_name
  -- Carimbos de data de estágio (funil) -------------------------------
  Became_Lead_Date                TIMESTAMP,  -- hs_lifecyclestage_lead_date
  Became_MQL_Date                 TIMESTAMP,  -- hs_lifecyclestage_marketingqualifiedlead_date
  Became_SQL_Date                 TIMESTAMP,  -- hs_lifecyclestage_salesqualifiedlead_date
  Became_Opportunity_Date         TIMESTAMP,  -- hs_lifecyclestage_opportunity_date
  Became_Customer_Date            TIMESTAMP,  -- hs_lifecyclestage_customer_date
  -- UTM (SE existirem como custom properties na conta Benner) ----------
  UTM_Source                      STRING,
  UTM_Medium                      STRING,
  UTM_Campaign                    STRING,
  hs_lastmodifieddate             TIMESTAMP,
  _synced_at                      TIMESTAMP
)
CLUSTER BY Contact_ID;


-- ---------------------------------------------------------------------
-- 3) Controle de sync (watermark) — opcional, se não usar MAX() direto
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `analytics-contas.03_MKT_SALES._hubspot_sync_state` (
  object_type   STRING,      -- 'deals' | 'contacts'
  watermark     TIMESTAMP,   -- último hs_lastmodifieddate processado
  updated_at    TIMESTAMP
);
