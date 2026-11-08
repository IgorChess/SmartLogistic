@@ dim_city
INSERT INTO core.dim_city (gc_id, city_id, city_name, region, full_name_local, latitude, longitude)
SELECT DISTINCT ON (c.gc_id)
       c.gc_id,
       c.id,
       c.name,
       CASE WHEN strpos(c.full_name_local, ',') > 0
            THEN NULLIF(btrim(substr(c.full_name_local, strpos(c.full_name_local, ',') + 1)), '')
       END,
       c.full_name_local,
       c.latitude,
       c.longitude
FROM cities c
ORDER BY c.gc_id, c.id
ON CONFLICT (gc_id) DO UPDATE SET
    city_id = EXCLUDED.city_id,
    city_name = EXCLUDED.city_name,
    region = EXCLUDED.region,
    full_name_local = EXCLUDED.full_name_local,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;
@@ dim_body_type
INSERT INTO core.dim_body_type (body_type_id, name, std_id, body_group)
SELECT bt.id,
       bt.name,
       bt.std_id,
       CASE COALESCE(bt.std_id, bt.id)
            WHEN 56 THEN 'Tent'
            WHEN 4  THEN 'Reefer'
            WHEN 2  THEN 'Isotherm'
            WHEN 15 THEN 'Flatbed'
            ELSE 'Other'
       END
FROM body_types bt
ON CONFLICT (body_type_id) DO UPDATE SET
    name = EXCLUDED.name,
    std_id = EXCLUDED.std_id,
    body_group = EXCLUDED.body_group;
