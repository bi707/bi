-- =====================================================================
-- HubSpot -> BigQuery | Views de modelagem + View final por ORIGEM + DATA
-- Dataset: analytics-contas.03_MKT_SALES
--
-- vw_hubspot_contacts_lifecycle : 1 linha por contato (+ campanha)
-- vw_hubspot_deals_stage        : deals + contato associado (origem + campanha)
-- vw_hubspot_stage_events       : unpivot dos carimbos v2 -> fato por data
-- vw_hubspot_leads_stages       : funil por origem + campanha + event_date (ESQUEMA PADRÃO)
-- + patch do UNION em vw_ads_crm_results (ramo HubSpot)
--
-- CAMPANHA: Campaign_ID = ID da campanha de Ads (para JOIN com as tabelas de
-- Ads no BigQuery). Campaign_Name é best-effort (utm_campaign da 1ª URL) e
-- pode ser NULL; por isso a coluna 'campanha' do esquema padrão usa
-- COALESCE(nome, ID).
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) Contatos (estado atual já é 1 linha/contato após o MERGE)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW `analytics-contas.03_MKT_SALES.vw_hubspot_contacts_lifecycle` AS
SELECT
  Contact_ID, Contact_Name, Contact_Email, Contact_Lifecycle_Stage,
  Contact_Created_At, Origem, Origem_Raw, Origem_Data_1, Origem_Data_2,
  Campaign_ID, Campaign_Name, Campaign_Keyword, First_URL,
  COALESCE(Campaign_Name, Campaign_ID) AS Campanha,
  Latest_Source, First_Conversion, First_Touch_Campaign,
  Became_Subscriber_Date, Became_Lead_Date, Became_MQL_Date, Became_SQL_Date,
  Became_Opportunity_Date, Became_Customer_Date
FROM `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts`;


-- ---------------------------------------------------------------------
-- 2) Deals + contato associado (origem e campanha herdadas do contato)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW `analytics-contas.03_MKT_SALES.vw_hubspot_deals_stage` AS
SELECT
  d.Deal_ID, d.Deal_Name, d.Pipeline_ID, d.Pipeline_Stage_ID, d.Deal_Status, d.Deal_Win,
  d.Deal_Amount, d.Deal_Currency, d.Deal_Created_Date, d.Deal_Closed_Date,
  COALESCE(NULLIF(c.Origem, 'Offline'), NULLIF(d.Deal_Source, 'Offline'),
           c.Origem, d.Deal_Source, 'Não informado')     AS Origem,
  d.Deal_Source                                           AS Deal_Origem_Propria,
  -- Campanha: ID do deal, senão do contato associado (chave de join com Ads)
  COALESCE(d.Campaign_ID, c.Campaign_ID)                  AS Campaign_ID,
  c.Campaign_Name                                         AS Campaign_Name,
  COALESCE(c.Campaign_Name, d.Campaign_ID, c.Campaign_ID) AS Campanha,
  d.Contact_ID, c.Contact_Email, c.Contact_Lifecycle_Stage
FROM `analytics-contas.03_MKT_SALES.Tb_HubSpot_Deals` d
LEFT JOIN `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts` c
  ON d.Contact_ID = c.Contact_ID;


-- ---------------------------------------------------------------------
-- 3) Fato de eventos de estágio (unpivot dos carimbos v2) + campanha
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW `analytics-contas.03_MKT_SALES.vw_hubspot_stage_events` AS
WITH contact_events AS (
  SELECT Contact_ID AS entity_id, Origem, COALESCE(Campaign_Name, Campaign_ID) AS campanha, Campaign_ID AS campaign_id, 'contact_created' AS stage, DATE(Contact_Created_At) AS event_date FROM `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts` WHERE Contact_Created_At IS NOT NULL
  UNION ALL SELECT Contact_ID, Origem, COALESCE(Campaign_Name, Campaign_ID), Campaign_ID, 'lead',        DATE(Became_Lead_Date)        FROM `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts` WHERE Became_Lead_Date IS NOT NULL
  UNION ALL SELECT Contact_ID, Origem, COALESCE(Campaign_Name, Campaign_ID), Campaign_ID, 'mql',         DATE(Became_MQL_Date)         FROM `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts` WHERE Became_MQL_Date IS NOT NULL
  UNION ALL SELECT Contact_ID, Origem, COALESCE(Campaign_Name, Campaign_ID), Campaign_ID, 'sql',         DATE(Became_SQL_Date)         FROM `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts` WHERE Became_SQL_Date IS NOT NULL
  UNION ALL SELECT Contact_ID, Origem, COALESCE(Campaign_Name, Campaign_ID), Campaign_ID, 'opportunity', DATE(Became_Opportunity_Date) FROM `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts` WHERE Became_Opportunity_Date IS NOT NULL
  UNION ALL SELECT Contact_ID, Origem, COALESCE(Campaign_Name, Campaign_ID), Campaign_ID, 'client',      DATE(Became_Customer_Date)    FROM `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts` WHERE Became_Customer_Date IS NOT NULL
),
deal_events AS (
  SELECT Deal_ID AS entity_id, Origem, Campanha AS campanha, Campaign_ID AS campaign_id, 'deal_created' AS stage, DATE(Deal_Created_Date) AS event_date FROM `analytics-contas.03_MKT_SALES.vw_hubspot_deals_stage` WHERE Deal_Created_Date IS NOT NULL
  UNION ALL SELECT Deal_ID, Origem, Campanha, Campaign_ID, 'deal_won',  DATE(Deal_Closed_Date) FROM `analytics-contas.03_MKT_SALES.vw_hubspot_deals_stage` WHERE Deal_Status = 'won'  AND Deal_Closed_Date IS NOT NULL
  UNION ALL SELECT Deal_ID, Origem, Campanha, Campaign_ID, 'deal_lost', DATE(Deal_Closed_Date) FROM `analytics-contas.03_MKT_SALES.vw_hubspot_deals_stage` WHERE Deal_Status = 'lost' AND Deal_Closed_Date IS NOT NULL
)
SELECT * FROM contact_events
UNION ALL
SELECT * FROM deal_events;


-- ---------------------------------------------------------------------
-- 4) FUNIL POR ORIGEM + CAMPANHA + DATA (esquema padronizado)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW `analytics-contas.03_MKT_SALES.vw_hubspot_leads_stages` AS
WITH agg AS (
  SELECT
    e.Origem                                                   AS origem,
    e.campanha                                                 AS campanha,
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
  GROUP BY origem, campanha, event_date
),
amt AS (   -- valor ganho por origem + campanha + data de fechamento
  SELECT Origem AS origem, Campanha AS campanha, DATE(Deal_Closed_Date) AS event_date, SUM(Deal_Amount) AS amount
  FROM `analytics-contas.03_MKT_SALES.vw_hubspot_deals_stage`
  WHERE Deal_Status = 'won' AND Deal_Closed_Date IS NOT NULL
  GROUP BY origem, campanha, event_date
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
  agg.campanha                         AS campanha,   -- nome (best-effort) OU ID da campanha de Ads
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
  CAST(NULL AS JSON)                   AS other_stages_json
FROM agg
LEFT JOIN amt USING (origem, campanha, event_date);


-- ---------------------------------------------------------------------
-- 5) JOIN com Ads por Campaign_ID (exemplo/base p/ a agência)
--    Liga contacts/deals do HubSpot às tabelas de spend de Ads pelo ID
--    da campanha. Ajustar o nome/coluna da tabela de Ads conforme o caso.
-- ---------------------------------------------------------------------
-- Ex.: leads pagos por campanha (id + nome-best-effort) e dia:
-- SELECT c.Campaign_ID, ANY_VALUE(c.Campaign_Name) AS campanha_nome,
--        DATE(c.Contact_Created_At) AS dia, COUNT(*) AS leads
-- FROM `analytics-contas.03_MKT_SALES.vw_hubspot_contacts_lifecycle` c
-- WHERE c.Campaign_ID IS NOT NULL
-- GROUP BY c.Campaign_ID, dia;
-- -> depois LEFT JOIN nas tabelas de Ads (ex.: Tabelas_Campanhas_Diario)
--    ON ads.campaign_id = c.Campaign_ID AND ads.dia = c.dia.


-- ---------------------------------------------------------------------
-- 6) PATCH da VIEW FINAL: ver sql/04_final_view_union.sql
--    (vw_ads_crm_results + ramo HubSpot; a coluna 'campanha' já vem
--     preenchida com nome-best-effort OU ID da campanha)
-- ---------------------------------------------------------------------
