@@ stg_prices
CREATE TEMP TABLE stg_prices ON COMMIT DROP AS
SELECT p.id                  AS price_id,
       p.created_at,
       p.organization_id,
       p.loading_date,
       p.end_loading_date,
       p.loading_city_gcid,
       p.unloading_city_gcid,
       p.distance,
       p.total_weight,
       p.total_volume,
       p.body_type,
       p.price,
       p.currency_code,
       p.complex,
       p.price_type,
       p.is_fact,
       p.nearest_rate_date,
       p.outlier_mark,
       NULLIF(btrim(p.weight_category), '') AS weight_category,
       fx.value              AS fx_rate,
       CASE
           WHEN p.price <= 0                                              THEN 'NON_POSITIVE_PRICE'
           WHEN p.currency_code = '643' AND p.price <= 1000               THEN 'RUB_PRICE_TOO_LOW'
           WHEN p.distance <= 0                                           THEN 'NON_POSITIVE_DISTANCE'
           WHEN p.total_weight < 0                                        THEN 'NEGATIVE_WEIGHT'
           WHEN p.total_volume < 0                                        THEN 'NEGATIVE_VOLUME'
           WHEN lc.gc_id IS NULL OR uc.gc_id IS NULL                      THEN 'UNKNOWN_CITY'
           WHEN p.currency_code NOT IN ('643', '840', '978')              THEN 'UNSUPPORTED_CURRENCY'
           WHEN p.currency_code <> '643' AND p.nearest_rate_date IS NULL  THEN 'NO_RATE_DATE'
           WHEN p.currency_code <> '643' AND fx.value IS NULL             THEN 'NO_FX_RATE'
       END AS reason_code
FROM prices p
LEFT JOIN core.dim_city lc ON lc.gc_id = p.loading_city_gcid
LEFT JOIN core.dim_city uc ON uc.gc_id = p.unloading_city_gcid
LEFT JOIN (
    SELECT DISTINCT ON (num_code, setting_date) num_code, setting_date, value
    FROM exchange_rates
    ORDER BY num_code, setting_date, id DESC
) fx ON fx.num_code = p.currency_code
    AND fx.setting_date = p.nearest_rate_date
    AND p.currency_code <> '643'
WHERE p.loading_date BETWEEN %(start_date)s AND %(end_date)s;
@@ stg_body
CREATE TEMP TABLE stg_body ON COMMIT DROP AS
SELECT s.price_id, COALESCE(bt.body_group, 'Other') AS body_group
FROM stg_prices s
JOIN price_body_types pbt ON pbt.price_id = s.price_id
LEFT JOIN core.dim_body_type bt ON bt.body_type_id = pbt.body_type_id
WHERE s.reason_code IS NULL
UNION
SELECT s.price_id, COALESCE(bt.body_group, 'Other')
FROM stg_prices s
LEFT JOIN core.dim_body_type bt ON bt.body_type_id = s.body_type
WHERE s.reason_code IS NULL
  AND s.body_type IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM price_body_types x WHERE x.price_id = s.price_id)
UNION
SELECT s.price_id, 'Unspecified'
FROM stg_prices s
WHERE s.reason_code IS NULL
  AND s.body_type IS NULL
  AND NOT EXISTS (SELECT 1 FROM price_body_types x WHERE x.price_id = s.price_id);
@@ delete_core
DELETE FROM core.fct_price WHERE loading_date BETWEEN %(start_date)s AND %(end_date)s;
@@ delete_quarantine
DELETE FROM core.dq_quarantine_prices WHERE loading_date BETWEEN %(start_date)s AND %(end_date)s;
@@ insert_quarantine
INSERT INTO core.dq_quarantine_prices (price_id, loading_date, reason_code, price, currency_code, nearest_rate_date)
SELECT price_id, loading_date, reason_code, price, currency_code, nearest_rate_date
FROM stg_prices
WHERE reason_code IS NOT NULL;
@@ insert_fct_price
INSERT INTO core.fct_price (
    price_id, created_at, organization_id, loading_date, end_loading_date,
    loading_city_gcid, unloading_city_gcid, distance, total_weight, total_volume,
    weight_category, volume_category, body_group_primary,
    price_raw, currency_code, fx_rate, price_rub,
    price_type, is_fact, complex, outlier_mark)
SELECT s.price_id, s.created_at, s.organization_id, s.loading_date, s.end_loading_date,
       s.loading_city_gcid, s.unloading_city_gcid, s.distance, s.total_weight, s.total_volume,
       COALESCE(s.weight_category,
           CASE
               WHEN round(s.total_weight::numeric, 1) >= 30   THEN 'G20T'
               WHEN round(s.total_weight::numeric, 1) >= 10   THEN 'FTL'
               WHEN round(s.total_weight::numeric, 1) >= 5    THEN '10T'
               WHEN round(s.total_weight::numeric, 1) >= 2.5  THEN '5T'
               WHEN round(s.total_weight::numeric, 1) >= 0.5  THEN 'L5T'
               ELSE 'OTH'
           END),
       CASE WHEN s.total_volume > 0 AND s.total_volume <= 120 THEN 'FTL' ELSE 'OTH' END,
       COALESCE(
           CASE WHEN s.body_type IS NOT NULL THEN COALESCE(bt.body_group, 'Other') END,
           (SELECT min(b.body_group) FROM stg_body b WHERE b.price_id = s.price_id),
           'Unspecified'),
       s.price,
       s.currency_code,
       CASE WHEN s.currency_code = '643' THEN 1.0 ELSE s.fx_rate END,
       s.price * CASE WHEN s.currency_code = '643' THEN 1.0 ELSE s.fx_rate END,
       s.price_type, s.is_fact, s.complex, s.outlier_mark
FROM stg_prices s
LEFT JOIN core.dim_body_type bt ON bt.body_type_id = s.body_type
WHERE s.reason_code IS NULL;
@@ insert_body_group
INSERT INTO core.fct_price_body_group (price_id, body_group)
SELECT price_id, body_group FROM stg_body;
@@ insert_price_month
INSERT INTO core.fct_price_month (price_id, price_date, price_month)
SELECT pd.price_id, pd.price_date, date_trunc('month', pd.price_date)::date
FROM price_dates pd
JOIN core.fct_price f ON f.price_id = pd.price_id
WHERE f.loading_date BETWEEN %(start_date)s AND %(end_date)s;
