-- =====================================================================
-- HubSpot → BigQuery | Views de modelagem + View final por ORIGEM + DATA
-- Dataset: analytics-contas.03_MKT_SALES
--
-- vw_hubspot_contacts_lifecycle : 1 linha por contato (dedup)
-- vw_hubspot_deals_stage        : deals + contato associado
-- vw_hubspot_stage_events       : unpivot dos carimbos de estágio -> fato por data
-- vw_hubspot_leads_stages       : funil por origem + event_date (ESQUEMA PADRÃO)
-- + patch do UNION em vw_ads_crm_results (adiciona o ramo HubSpot)
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) Contatos (estado atual já é 1 linha/contato após o MERGE)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW `analytics-contas.03_MKT_SALES.vw_hubspot_contacts_lifecycle` AS
SELECT
  Contact_ID, Contact_Name, Contact_Email, Contact_Lifecycle_Stage,
  Contact_Created_At, Origem, Origem_Raw, Origem_Data_1, Origem_Data_2,
  Latest_Source, First_Conversion, Last_Conversion,
  Became_Lead_Date, Became_MQL_Date, Became_SQL_Date,
  Became_Opportunity_Date, Became_Customer_Date,
  UTM_Source, UTM_Medium, UTM_Campaign
FROM `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts`;


-- ---------------------------------------------------------------------
-- 2) Deals + contato associado (equivale a vw_rdcrm_deals_stage)
--    Enriquece a origem do deal com a origem do contato quando faltar.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW `analytics-contas.03_MKT_SALES.vw_hubspot_deals_stage` AS
SELECT
  d.Deal_ID, d.Deal_Name, d.Pipeline, d.Deal_Stage, d.Deal_Status, d.Deal_Win,
  d.Deal_Amount, d.Deal_Created_Date, d.Deal_Closed_Date,
  COALESCE(NULLIF(d.Deal_Source, 'Não informado'), c.Origem, 'Não informado') AS Origem,
  d.Contact_ID, COALESCE(d.Contact_Email, c.Contact_Email) AS Contact_Email,
  c.Contact_Lifecycle_Stage, c.UTM_Source, c.UTM_Medium, c.UTM_Campaign
FROM `analytics-contas.03_MKT_SALES.Tb_HubSpot_Deals` d
LEFT JOIN `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts` c
  ON d.Contact_ID = c.Contact_ID;


-- ---------------------------------------------------------------------
-- 3) Fato de eventos de estágio (unpivot dos carimbos de data)
--    Cada linha = 1 objeto entrou em 1 estágio numa data.
--    É o que permite contar o funil pela DATA em que o estágio ocorreu.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW `analytics-contas.03_MKT_SALES.vw_hubspot_stage_events` AS
WITH contact_events AS (
  SELECT Contact_ID AS entity_id, Origem, 'contact_created' AS stage, DATE(Contact_Created_At)      AS event_date FROM `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts` WHERE Contact_Created_At IS NOT NULL
  UNION ALL
  SELECT Contact_ID, Origem, 'lead',        DATE(Became_Lead_Date)        FROM `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts` WHERE Became_Lead_Date IS NOT NULL
  UNION ALL
  SELECT Contact_ID, Origem, 'mql',         DATE(Became_MQL_Date)         FROM `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts` WHERE Became_MQL_Date IS NOT NULL
  UNION ALL
  SELECT Contact_ID, Origem, 'sql',         DATE(Became_SQL_Date)         FROM `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts` WHERE Became_SQL_Date IS NOT NULL
  UNION ALL
  SELECT Contact_ID, Origem, 'opportunity', DATE(Became_Opportunity_Date) FROM `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts` WHERE Became_Opportunity_Date IS NOT NULL
  UNION ALL
  SELECT Contact_ID, Origem, 'client',      DATE(Became_Customer_Date)    FROM `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts` WHERE Became_Customer_Date IS NOT NULL
),
deal_events AS (
  SELECT Deal_ID AS entity_id, Origem, 'deal_created', DATE(Deal_Created_Date) FROM `analytics-contas.03_MKT_SALES.vw_hubspot_deals_stage` WHERE Deal_Created_Date IS NOT NULL
  UNION ALL
  SELECT Deal_ID, Origem, 'deal_won',  DATE(Deal_Closed_Date) FROM `analytics-contas.03_MKT_SALES.vw_hubspot_deals_stage` WHERE Deal_Win = TRUE  AND Deal_Closed_Date IS NOT NULL
  UNION ALL
  SELECT Deal_ID, Origem, 'deal_lost', DATE(Deal_Closed_Date) FROM `analytics-contas.03_MKT_SALES.vw_hubspot_deals_stage` WHERE Deal_Status = 'lost' AND Deal_Closed_Date IS NOT NULL
)
SELECT * FROM contact_events
UNION ALL
SELECT * FROM deal_events;


-- ---------------------------------------------------------------------
-- 4) FUNIL POR ORIGEM + DATA  (esquema padronizado, igual vw_rd_leads_stages)
--    Consumível direto e pronto para o UNION em vw_ads_crm_results.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW `analytics-contas.03_MKT_SALES.vw_hubspot_leads_stages` AS
WITH agg AS (
  SELECT
    e.Origem                                                   AS origem,
    e.event_date                                               AS event_date,
    COUNT(IF(e.stage = 'contact_created', e.entity_id, NULL))  AS contacts,
    COUNT(IF(e.stage = 'lead',            e.entity_id, NULL))  AS leads,
    COUNT(IF(e.stage = 'mql',             e.entity_id, NULL))  AS lifecycle_stage_mql,
    COUNT(IF(e.stage = 'sql',             e.entity_id, NULL))  AS lifecycle_stage_sql,
    COUNT(IF(e.stage = 'opportunity',     e.entity_id, NULL))  AS opportunities,
    COUNT(IF(e.stage = 'deal_created',    e.entity_id, NULL))  AS deals_created,
    COUNT(IF(e.stage IN ('deal_won','deal_lost'), e.entity_id, NULL)) AS deals_closed,
    COUNT(IF(e.stage = 'deal_lost',       e.entity_id, NULL))  AS deals_lost,
    COUNT(IF(e.stage = 'deal_won',        e.entity_id, NULL))  AS deals_won,
    COUNT(IF(e.stage = 'client',          e.entity_id, NULL))  AS clients,
    COUNT(DISTINCT e.entity_id)                                AS deals_moved_any_stage
  FROM `analytics-contas.03_MKT_SALES.vw_hubspot_stage_events` e
  GROUP BY origem, event_date
),
amt AS (   -- valor ganho por origem + data de fechamento
  SELECT Origem AS origem, DATE(Deal_Closed_Date) AS event_date, SUM(Deal_Amount) AS amount
  FROM `analytics-contas.03_MKT_SALES.vw_hubspot_deals_stage`
  WHERE Deal_Win = TRUE AND Deal_Closed_Date IS NOT NULL
  GROUP BY origem, event_date
)
SELECT
  CAST(NULL AS STRING)                 AS account_id,
  CAST(NULL AS STRING)                 AS account_name,
  CAST(NULL AS STRING)                 AS pipeline_name,
  agg.event_date                       AS event_date,
  CAST(NULL AS STRING)                 AS Deal_Source,
  CAST(NULL AS STRING)                 AS UTM_Campaign,
  CAST(NULL AS STRING)                 AS UTM_Medium,
  CAST(NULL AS STRING)                 AS UTM_Source,
  agg.origem                           AS origem,
  CAST(NULL AS STRING)                 AS Deal_Lost_Reason,
  CAST(NULL AS STRING)                 AS campanha,
  CAST(NULL AS STRING)                 AS grupo_anuncio,
  0                                    AS custo,
  0                                    AS impressoes,
  0                                    AS cliques,
  0                                    AS resultados,
  0                                    AS cadastros,
  0                                    AS visitas,
  agg.contacts, agg.leads, agg.lifecycle_stage_mql, agg.lifecycle_stage_sql,
  agg.opportunities, agg.deals_created, agg.deals_closed, agg.deals_lost,
  agg.deals_won, agg.clients, agg.deals_moved_any_stage,
  IFNULL(amt.amount, 0)                AS amount,
  TO_JSON_STRING(STRUCT<x STRING>(NULL)) AS other_stages_json
FROM agg
LEFT JOIN amt USING (origem, event_date);


-- ---------------------------------------------------------------------
-- 5) PATCH da VIEW FINAL: adicionar o ramo HubSpot ao UNION existente.
--    Cole o CTE abaixo em vw_ads_crm_results e acrescente
--    "UNION ALL SELECT * FROM hs" ao final. As colunas/ordem já batem
--    com os ramos "ads" e "rd".
-- ---------------------------------------------------------------------
--
-- hs AS (
--   SELECT
--     account_id, account_name, pipeline_name,
--     SAFE_CAST(event_date AS DATE)              AS data,
--     DATE_TRUNC(event_date, MONTH)              AS mes,
--     EXTRACT(ISOWEEK FROM event_date)           AS semana,
--     Deal_Source, UTM_Campaign, UTM_Medium, UTM_Source, origem, Deal_Lost_Reason,
--     campanha, grupo_anuncio,
--     custo, impressoes, cliques, resultados, cadastros,
--     visitas, contacts, leads, lifecycle_stage_mql, lifecycle_stage_sql,
--     opportunities, deals_created, deals_closed, deals_lost, deals_won,
--     clients, deals_moved_any_stage, amount,
--     'analytics-contas.03_MKT_SALES.vw_hubspot_leads_stages' AS source_table
--   FROM `analytics-contas.03_MKT_SALES.vw_hubspot_leads_stages`
-- )
-- ...
-- SELECT * FROM ads
-- UNION ALL SELECT * FROM rd
-- UNION ALL SELECT * FROM hs;
