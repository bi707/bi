-- =====================================================================
-- VIEW FINAL consolidada — vw_ads_crm_results + ramo HubSpot
-- Dataset: analytics-contas.03_MKT_SALES
--
-- Recria a view que a agência já consome, adicionando um 3º ramo no UNION
-- (source_table = '...vw_hubspot_leads_stages'), lado a lado com Ads e RD,
-- comparável por origem + data. Os ramos "ads" e "rd" são os originais,
-- inalterados; só foi acrescentado o CTE "hs" e o "UNION ALL SELECT * FROM hs".
--
-- ⚠️ Aplicar substitui a view de produção. Revise antes de rodar.
-- =====================================================================

CREATE OR REPLACE VIEW `analytics-contas.03_MKT_SALES.vw_ads_crm_results` AS
WITH ads AS (
  SELECT
    CAST(id_do_cliente AS STRING)   AS account_id,
    CAST(nome_da_conta AS STRING)   AS account_name,
    CAST(pipeline_name AS STRING)   AS pipeline_name,
    SAFE_CAST(dia AS DATE)          AS data,
    DATE_TRUNC(dia, MONTH)          AS mes,
    EXTRACT(ISOWEEK FROM dia)       AS semana,
    CAST(Deal_Source AS STRING)     AS Deal_Source,
    CAST(UTM_Campaign AS STRING)    AS UTM_Campaign,
    CAST(UTM_Medium AS STRING)      AS UTM_Medium,
    CAST(UTM_Source AS STRING)      AS UTM_Source,
    CAST(origem AS STRING)          AS origem,
    CAST(Deal_Lost_Reason AS STRING) AS Deal_Lost_Reason,
    CAST(campanha AS STRING)        AS campanha,
    CAST(grupo_anuncio AS STRING)   AS grupo_anuncio,
    SAFE_CAST(custo AS FLOAT64)     AS custo,
    SAFE_CAST(impressoes AS INT64)  AS impressoes,
    SAFE_CAST(cliques AS INT64)     AS cliques,
    SAFE_CAST(resultados AS INT64)  AS resultados,
    SAFE_CAST(cadastros AS INT64)   AS cadastros,
    SAFE_CAST(visitas AS INT64)     AS visitas,
    SAFE_CAST(contacts AS INT64)    AS contacts,
    SAFE_CAST(leads AS INT64)       AS leads,
    SAFE_CAST(lifecycle_stage_mql AS INT64) AS lifecycle_stage_mql,
    SAFE_CAST(lifecycle_stage_sql AS INT64) AS lifecycle_stage_sql,
    SAFE_CAST(opportunities AS INT64) AS opportunities,
    SAFE_CAST(deals_created AS INT64) AS deals_created,
    SAFE_CAST(deals_closed AS INT64)  AS deals_closed,
    SAFE_CAST(deals_lost AS INT64)    AS deals_lost,
    SAFE_CAST(deals_won AS INT64)     AS deals_won,
    SAFE_CAST(clients AS INT64)       AS clients,
    SAFE_CAST(deals_moved_any_stage AS INT64) AS deals_moved_any_stage,
    SAFE_CAST(ammount AS FLOAT64)     AS amount,
    'analytics-contas.03_MKT_SALES.vw_ads_campanhas' AS source_table
  FROM `analytics-contas.03_MKT_SALES.vw_ads_campanhas`
),
rd AS (
  SELECT
    CAST(account_id AS STRING)      AS account_id,
    CAST(account_name AS STRING)    AS account_name,
    CAST(pipeline_name AS STRING)   AS pipeline_name,
    SAFE_CAST(event_date AS DATE)   AS data,
    DATE_TRUNC(event_date, MONTH)   AS mes,
    EXTRACT(ISOWEEK FROM event_date) AS semana,
    CAST(Deal_Source AS STRING)     AS Deal_Source,
    CAST(UTM_Campaign AS STRING)    AS UTM_Campaign,
    CAST(UTM_Medium AS STRING)      AS UTM_Medium,
    CAST(UTM_Source AS STRING)      AS UTM_Source,
    CAST(origem AS STRING)          AS origem,
    CAST(Deal_Lost_Reason AS STRING) AS Deal_Lost_Reason,
    CAST(campanha AS STRING)        AS campanha,
    CAST(NULL AS STRING)            AS grupo_anuncio,
    CAST(NULL AS FLOAT64)           AS custo,
    CAST(NULL AS INT64)             AS impressoes,
    CAST(NULL AS INT64)             AS cliques,
    CAST(NULL AS INT64)             AS resultados,
    CAST(NULL AS INT64)             AS cadastros,
    SAFE_CAST(visitas AS INT64)     AS visitas,
    SAFE_CAST(contacts AS INT64)    AS contacts,
    SAFE_CAST(leads AS INT64)       AS leads,
    SAFE_CAST(lifecycle_stage_mql AS INT64) AS lifecycle_stage_mql,
    SAFE_CAST(lifecycle_stage_sql AS INT64) AS lifecycle_stage_sql,
    SAFE_CAST(opportunities AS INT64) AS opportunities,
    SAFE_CAST(deals_created AS INT64) AS deals_created,
    SAFE_CAST(deals_closed AS INT64)  AS deals_closed,
    SAFE_CAST(deals_lost AS INT64)    AS deals_lost,
    SAFE_CAST(deals_won AS INT64)     AS deals_won,
    SAFE_CAST(clients AS INT64)       AS clients,
    SAFE_CAST(deals_moved_any_stage AS INT64) AS deals_moved_any_stage,
    SAFE_CAST(amount AS FLOAT64)      AS amount,
    'analytics-contas.03_MKT_SALES.vw_rd_leads_stages' AS source_table
  FROM `analytics-contas.03_MKT_SALES.vw_rd_leads_stages`
),
hs AS (   -- >>> NOVO: ramo HubSpot <<<
  SELECT
    account_id, account_name, pipeline_name,
    SAFE_CAST(event_date AS DATE)   AS data,
    DATE_TRUNC(event_date, MONTH)   AS mes,
    EXTRACT(ISOWEEK FROM event_date) AS semana,
    Deal_Source, UTM_Campaign, UTM_Medium, UTM_Source, origem, Deal_Lost_Reason,
    campanha, grupo_anuncio,
    SAFE_CAST(custo AS FLOAT64)     AS custo,
    SAFE_CAST(impressoes AS INT64)  AS impressoes,
    SAFE_CAST(cliques AS INT64)     AS cliques,
    SAFE_CAST(resultados AS INT64)  AS resultados,
    SAFE_CAST(cadastros AS INT64)   AS cadastros,
    SAFE_CAST(visitas AS INT64)     AS visitas,
    contacts, leads, lifecycle_stage_mql, lifecycle_stage_sql,
    opportunities, deals_created, deals_closed, deals_lost, deals_won,
    clients, deals_moved_any_stage,
    SAFE_CAST(amount AS FLOAT64)    AS amount,
    'analytics-contas.03_MKT_SALES.vw_hubspot_leads_stages' AS source_table
  FROM `analytics-contas.03_MKT_SALES.vw_hubspot_leads_stages`
)
SELECT * FROM ads
UNION ALL SELECT * FROM rd
UNION ALL SELECT * FROM hs;
