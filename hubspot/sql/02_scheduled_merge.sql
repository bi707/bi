-- =====================================================================
-- HubSpot → BigQuery | Scheduled Queries de MERGE (RAW → CLEAN)
-- Rodar logo após o n8n fazer o append no raw (ex.: Scheduled Query a
-- cada 1h, ou disparado pelo próprio n8n via nó BigQuery "query").
--
-- Ideia: deduplicar o raw (pegar a versão mais recente por id) e fazer
-- UPSERT na tabela CLEAN. Resolve a duplicação típica do schedule.
-- Os JSON_VALUE(...) abaixo assumem que _raw guarda o objeto com um nó
-- "properties". Ajustar os paths após validar o payload real (§5).
-- =====================================================================

-- ---------------------------------------------------------------------
-- DEALS
-- ---------------------------------------------------------------------
MERGE `analytics-contas.03_MKT_SALES.Tb_HubSpot_Deals` T
USING (
  SELECT * FROM (
    SELECT
      Deal_ID,
      JSON_VALUE(_raw, '$.properties.dealname')                         AS Deal_Name,
      JSON_VALUE(_raw, '$.properties.pipeline')                         AS Pipeline,
      JSON_VALUE(_raw, '$.properties.dealstage')                        AS Pipeline_Stage_ID,
      JSON_VALUE(_raw, '$.properties.dealstage')                        AS Deal_Stage,          -- resolver rótulo depois
      CASE
        WHEN JSON_VALUE(_raw, '$.properties.hs_is_closed_won') = 'true' THEN 'won'
        WHEN JSON_VALUE(_raw, '$.properties.hs_is_closed')     = 'true' THEN 'lost'
        ELSE 'open'
      END                                                               AS Deal_Status,
      JSON_VALUE(_raw, '$.properties.hs_is_closed_won') = 'true'        AS Deal_Win,
      SAFE_CAST(JSON_VALUE(_raw, '$.properties.amount') AS NUMERIC)      AS Deal_Amount,
      SAFE_CAST(JSON_VALUE(_raw, '$.properties.createdate') AS TIMESTAMP) AS Deal_Created_Date,
      SAFE_CAST(JSON_VALUE(_raw, '$.properties.closedate')  AS TIMESTAMP) AS Deal_Closed_Date,
      JSON_VALUE(_raw, '$.properties.hs_analytics_source')              AS Deal_Source_Raw,
      -- de-para de origem
      CASE JSON_VALUE(_raw, '$.properties.hs_analytics_source')
        WHEN 'ORGANIC_SEARCH'  THEN 'Busca Orgânica'
        WHEN 'PAID_SEARCH'     THEN 'Busca Paga'
        WHEN 'PAID_SOCIAL'     THEN 'Social Pago'
        WHEN 'SOCIAL_MEDIA'    THEN 'Social Orgânico'
        WHEN 'EMAIL_MARKETING' THEN 'E-mail Marketing'
        WHEN 'REFERRALS'       THEN 'Referência'
        WHEN 'OTHER_CAMPAIGNS' THEN 'Outras Campanhas'
        WHEN 'DIRECT_TRAFFIC'  THEN 'Tráfego Direto'
        WHEN 'OFFLINE'         THEN 'Offline'
        ELSE 'Não informado'
      END                                                               AS Deal_Source,
      JSON_VALUE(_raw, '$.properties.hs_analytics_source_data_1')       AS Deal_Source_Data_1,
      JSON_VALUE(_raw, '$.properties.hs_analytics_source_data_2')       AS Deal_Source_Data_2,
      JSON_VALUE(_raw, '$.associations.contacts.results[0].id')         AS Contact_ID,
      JSON_VALUE(_raw, '$.properties.email')                            AS Contact_Email,
      hs_lastmodifieddate,
      _synced_at,
      ROW_NUMBER() OVER (PARTITION BY Deal_ID ORDER BY hs_lastmodifieddate DESC, _synced_at DESC) AS rn
    FROM `analytics-contas.03_MKT_SALES.raw_hubspot_deals`
  )
  WHERE rn = 1
) S
ON T.Deal_ID = S.Deal_ID
WHEN MATCHED AND S.hs_lastmodifieddate > T.hs_lastmodifieddate THEN UPDATE SET
  Deal_Name = S.Deal_Name, Pipeline = S.Pipeline, Pipeline_Stage_ID = S.Pipeline_Stage_ID,
  Deal_Stage = S.Deal_Stage, Deal_Status = S.Deal_Status, Deal_Win = S.Deal_Win,
  Deal_Amount = S.Deal_Amount, Deal_Created_Date = S.Deal_Created_Date,
  Deal_Closed_Date = S.Deal_Closed_Date, Deal_Source_Raw = S.Deal_Source_Raw,
  Deal_Source = S.Deal_Source, Deal_Source_Data_1 = S.Deal_Source_Data_1,
  Deal_Source_Data_2 = S.Deal_Source_Data_2, Contact_ID = S.Contact_ID,
  Contact_Email = S.Contact_Email, hs_lastmodifieddate = S.hs_lastmodifieddate,
  _synced_at = S._synced_at
WHEN NOT MATCHED THEN INSERT (
  Deal_ID, Deal_Name, Pipeline, Pipeline_Stage_ID, Deal_Stage, Deal_Status, Deal_Win,
  Deal_Amount, Deal_Created_Date, Deal_Closed_Date, Deal_Source_Raw, Deal_Source,
  Deal_Source_Data_1, Deal_Source_Data_2, Contact_ID, Contact_Email,
  hs_lastmodifieddate, _synced_at
) VALUES (
  S.Deal_ID, S.Deal_Name, S.Pipeline, S.Pipeline_Stage_ID, S.Deal_Stage, S.Deal_Status, S.Deal_Win,
  S.Deal_Amount, S.Deal_Created_Date, S.Deal_Closed_Date, S.Deal_Source_Raw, S.Deal_Source,
  S.Deal_Source_Data_1, S.Deal_Source_Data_2, S.Contact_ID, S.Contact_Email,
  S.hs_lastmodifieddate, S._synced_at
);


-- ---------------------------------------------------------------------
-- CONTACTS
-- ---------------------------------------------------------------------
MERGE `analytics-contas.03_MKT_SALES.Tb_HubSpot_Contacts` T
USING (
  SELECT * FROM (
    SELECT
      Contact_ID,
      TRIM(CONCAT(
        IFNULL(JSON_VALUE(_raw, '$.properties.firstname'), ''), ' ',
        IFNULL(JSON_VALUE(_raw, '$.properties.lastname'),  '')))         AS Contact_Name,
      JSON_VALUE(_raw, '$.properties.email')                             AS Contact_Email,
      JSON_VALUE(_raw, '$.properties.lifecyclestage')                    AS Contact_Lifecycle_Stage,
      SAFE_CAST(JSON_VALUE(_raw, '$.properties.createdate') AS TIMESTAMP) AS Contact_Created_At,
      JSON_VALUE(_raw, '$.properties.hs_analytics_source')               AS Origem_Raw,
      CASE JSON_VALUE(_raw, '$.properties.hs_analytics_source')
        WHEN 'ORGANIC_SEARCH'  THEN 'Busca Orgânica'
        WHEN 'PAID_SEARCH'     THEN 'Busca Paga'
        WHEN 'PAID_SOCIAL'     THEN 'Social Pago'
        WHEN 'SOCIAL_MEDIA'    THEN 'Social Orgânico'
        WHEN 'EMAIL_MARKETING' THEN 'E-mail Marketing'
        WHEN 'REFERRALS'       THEN 'Referência'
        WHEN 'OTHER_CAMPAIGNS' THEN 'Outras Campanhas'
        WHEN 'DIRECT_TRAFFIC'  THEN 'Tráfego Direto'
        WHEN 'OFFLINE'         THEN 'Offline'
        ELSE 'Não informado'
      END                                                                AS Origem,
      JSON_VALUE(_raw, '$.properties.hs_analytics_source_data_1')        AS Origem_Data_1,
      JSON_VALUE(_raw, '$.properties.hs_analytics_source_data_2')        AS Origem_Data_2,
      JSON_VALUE(_raw, '$.properties.hs_latest_source')                  AS Latest_Source,
      JSON_VALUE(_raw, '$.properties.first_conversion_event_name')       AS First_Conversion,
      JSON_VALUE(_raw, '$.properties.recent_conversion_event_name')      AS Last_Conversion,
      SAFE_CAST(JSON_VALUE(_raw, '$.properties.hs_lifecyclestage_lead_date')                   AS TIMESTAMP) AS Became_Lead_Date,
      SAFE_CAST(JSON_VALUE(_raw, '$.properties.hs_lifecyclestage_marketingqualifiedlead_date') AS TIMESTAMP) AS Became_MQL_Date,
      SAFE_CAST(JSON_VALUE(_raw, '$.properties.hs_lifecyclestage_salesqualifiedlead_date')     AS TIMESTAMP) AS Became_SQL_Date,
      SAFE_CAST(JSON_VALUE(_raw, '$.properties.hs_lifecyclestage_opportunity_date')            AS TIMESTAMP) AS Became_Opportunity_Date,
      SAFE_CAST(JSON_VALUE(_raw, '$.properties.hs_lifecyclestage_customer_date')               AS TIMESTAMP) AS Became_Customer_Date,
      JSON_VALUE(_raw, '$.properties.utm_source')                        AS UTM_Source,    -- custom? validar
      JSON_VALUE(_raw, '$.properties.utm_medium')                        AS UTM_Medium,    -- custom? validar
      JSON_VALUE(_raw, '$.properties.utm_campaign')                      AS UTM_Campaign,  -- custom? validar
      hs_lastmodifieddate,
      _synced_at,
      ROW_NUMBER() OVER (PARTITION BY Contact_ID ORDER BY hs_lastmodifieddate DESC, _synced_at DESC) AS rn
    FROM `analytics-contas.03_MKT_SALES.raw_hubspot_contacts`
  )
  WHERE rn = 1
) S
ON T.Contact_ID = S.Contact_ID
WHEN MATCHED AND S.hs_lastmodifieddate > T.hs_lastmodifieddate THEN UPDATE SET
  Contact_Name = S.Contact_Name, Contact_Email = S.Contact_Email,
  Contact_Lifecycle_Stage = S.Contact_Lifecycle_Stage, Contact_Created_At = S.Contact_Created_At,
  Origem_Raw = S.Origem_Raw, Origem = S.Origem, Origem_Data_1 = S.Origem_Data_1,
  Origem_Data_2 = S.Origem_Data_2, Latest_Source = S.Latest_Source,
  First_Conversion = S.First_Conversion, Last_Conversion = S.Last_Conversion,
  Became_Lead_Date = S.Became_Lead_Date, Became_MQL_Date = S.Became_MQL_Date,
  Became_SQL_Date = S.Became_SQL_Date, Became_Opportunity_Date = S.Became_Opportunity_Date,
  Became_Customer_Date = S.Became_Customer_Date, UTM_Source = S.UTM_Source,
  UTM_Medium = S.UTM_Medium, UTM_Campaign = S.UTM_Campaign,
  hs_lastmodifieddate = S.hs_lastmodifieddate, _synced_at = S._synced_at
WHEN NOT MATCHED THEN INSERT (
  Contact_ID, Contact_Name, Contact_Email, Contact_Lifecycle_Stage, Contact_Created_At,
  Origem_Raw, Origem, Origem_Data_1, Origem_Data_2, Latest_Source, First_Conversion,
  Last_Conversion, Became_Lead_Date, Became_MQL_Date, Became_SQL_Date,
  Became_Opportunity_Date, Became_Customer_Date, UTM_Source, UTM_Medium, UTM_Campaign,
  hs_lastmodifieddate, _synced_at
) VALUES (
  S.Contact_ID, S.Contact_Name, S.Contact_Email, S.Contact_Lifecycle_Stage, S.Contact_Created_At,
  S.Origem_Raw, S.Origem, S.Origem_Data_1, S.Origem_Data_2, S.Latest_Source, S.First_Conversion,
  S.Last_Conversion, S.Became_Lead_Date, S.Became_MQL_Date, S.Became_SQL_Date,
  S.Became_Opportunity_Date, S.Became_Customer_Date, S.UTM_Source, S.UTM_Medium, S.UTM_Campaign,
  S.hs_lastmodifieddate, S._synced_at
);
