SELECT (SELECT count(*) FROM prices)                     AS source_rows,
       (SELECT count(*) FROM core.fct_price)             AS core_rows,
       (SELECT count(*) FROM core.dq_quarantine_prices)  AS quarantine_rows;

SELECT reason_code, count(*) FROM core.dq_quarantine_prices GROUP BY 1 ORDER BY 2 DESC;

SELECT count(*) - count(DISTINCT price_id) AS dup_prices FROM core.fct_price;

SELECT count(*) AS dup_body_groups FROM (
    SELECT price_id, body_group FROM core.fct_price_body_group GROUP BY 1, 2 HAVING count(*) > 1) t;

SELECT gc_id, city_name, region, city_id FROM core.dim_city WHERE gc_id IN (1001, 1003);

SELECT month_start, p25_trip, median_trip, p75_trip, avg_trip, median_km,
       trips_count, carriers_count, round(cv_rate::numeric, 3) AS cv, round(mom_pct::numeric, 1) AS mom,
       round(yoy_pct::numeric, 1) AS yoy, reliability_level
FROM mart.route_card
WHERE loading_city_gcid = 1001 AND unloading_city_gcid = 1003
  AND body_group = 'Tent' AND weight_category = 'FTL'
ORDER BY month_start DESC LIMIT 6;

SELECT max(month_start) AS last_month, count(*) FILTER (WHERE month_start > as_of) AS future_rows FROM mart.route_card;

SELECT reliability_level, count(*) FROM mart.route_card GROUP BY 1 ORDER BY 1;

SELECT * FROM mart.ml_model_metrics ORDER BY model_name;

SELECT split, count(*), round(avg(ape_pct)::numeric, 2) AS mape_pct, round(avg(abs_error_rub)::numeric, 0) AS mae
FROM mart.ml_price_predictions GROUP BY 1;

SELECT count(*) AS bad_future_rows FROM mart.ml_price_predictions
WHERE split = 'future' AND (actual_price_rub IS NOT NULL OR abs_error_rub IS NOT NULL OR ape_pct IS NOT NULL);
