@@ truncate_mart
TRUNCATE mart.route_card;
@@ build_mart
WITH month_rows AS (
    SELECT DISTINCT price_id, price_month
    FROM core.fct_price_month
    WHERE price_date <= %(as_of)s::date
),
facts AS (
    SELECT m.price_month                      AS month_start,
           f.loading_city_gcid,
           f.unloading_city_gcid,
           bg.body_group,
           f.weight_category,
           f.price_id,
           f.price_rub,
           f.price_rub / NULLIF(f.distance, 0) AS price_km,
           f.organization_id,
           f.price_type
    FROM core.fct_price f
    JOIN month_rows m                 ON m.price_id  = f.price_id
    JOIN core.fct_price_body_group bg ON bg.price_id = f.price_id
    WHERE f.is_fact
      AND NOT f.complex
      AND NOT f.outlier_mark
      AND f.price_rub > 0
      AND f.distance > 0
),
cell AS (
    SELECT month_start, loading_city_gcid, unloading_city_gcid, body_group, weight_category,
           count(DISTINCT price_id)                                              AS trips_count,
           count(DISTINCT organization_id) FILTER (WHERE price_type IN (3, 9))   AS carriers_count,
           percentile_cont(0.25) WITHIN GROUP (ORDER BY price_rub)               AS p25_trip,
           percentile_cont(0.50) WITHIN GROUP (ORDER BY price_rub)               AS median_trip,
           percentile_cont(0.75) WITHIN GROUP (ORDER BY price_rub)               AS p75_trip,
           avg(price_rub)                                                        AS avg_trip,
           percentile_cont(0.25) WITHIN GROUP (ORDER BY price_km)                AS p25_km,
           percentile_cont(0.50) WITHIN GROUP (ORDER BY price_km)                AS median_km,
           percentile_cont(0.75) WITHIN GROUP (ORDER BY price_km)                AS p75_km,
           CASE WHEN count(*) >= 2 AND avg(price_rub) <> 0
                THEN stddev_samp(price_rub) / avg(price_rub) END                 AS cv_rate
    FROM facts
    GROUP BY month_start, loading_city_gcid, unloading_city_gcid, body_group, weight_category
)
INSERT INTO mart.route_card (
    month_start, loading_city_gcid, unloading_city_gcid, loading_city, unloading_city,
    body_group, weight_category,
    p25_trip, median_trip, p75_trip, avg_trip, p25_km, median_km, p75_km,
    trips_count, carriers_count, cv_rate, mom_pct, yoy_pct, reliability_level, as_of)
SELECT c.month_start, c.loading_city_gcid, c.unloading_city_gcid, lc.city_name, uc.city_name,
       c.body_group, c.weight_category,
       c.p25_trip, c.median_trip, c.p75_trip, c.avg_trip, c.p25_km, c.median_km, c.p75_km,
       c.trips_count, c.carriers_count, c.cv_rate,
       (c.median_trip - prev.median_trip) / NULLIF(prev.median_trip, 0) * 100,
       (c.median_trip - yoy.median_trip)  / NULLIF(yoy.median_trip, 0)  * 100,
       CASE
           WHEN c.trips_count >= 30 AND c.carriers_count >= 5
                AND (%(as_of)s::date - LEAST(%(as_of)s::date, ((c.month_start + INTERVAL '1 month')::date - 1))) <= 30
                THEN 'HIGH'
           WHEN c.trips_count >= 10 THEN 'MEDIUM'
           ELSE 'LOW_DATA'
       END,
       %(as_of)s::date
FROM cell c
LEFT JOIN core.dim_city lc ON lc.gc_id = c.loading_city_gcid
LEFT JOIN core.dim_city uc ON uc.gc_id = c.unloading_city_gcid
LEFT JOIN cell prev
       ON prev.loading_city_gcid = c.loading_city_gcid AND prev.unloading_city_gcid = c.unloading_city_gcid
      AND prev.body_group = c.body_group AND prev.weight_category = c.weight_category
      AND prev.month_start = (c.month_start - INTERVAL '1 month')::date
LEFT JOIN cell yoy
       ON yoy.loading_city_gcid = c.loading_city_gcid AND yoy.unloading_city_gcid = c.unloading_city_gcid
      AND yoy.body_group = c.body_group AND yoy.weight_category = c.weight_category
      AND yoy.month_start = (c.month_start - INTERVAL '1 year')::date;
