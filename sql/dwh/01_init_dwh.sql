CREATE SCHEMA IF NOT EXISTS core;
@@
CREATE SCHEMA IF NOT EXISTS mart;
@@
CREATE TABLE IF NOT EXISTS core.etl_run_log (
    run_id           bigserial PRIMARY KEY,
    step             text        NOT NULL,
    window_start     date,
    window_end       date,
    rows_read        integer,
    rows_loaded      integer,
    rows_quarantined integer,
    finished_at      timestamptz NOT NULL DEFAULT now()
);
@@
CREATE TABLE IF NOT EXISTS core.dim_city (
    gc_id           integer PRIMARY KEY,
    city_id         bigint  NOT NULL,
    city_name       text    NOT NULL,
    region          text,
    full_name_local text    NOT NULL,
    latitude        double precision,
    longitude       double precision
);
@@
CREATE TABLE IF NOT EXISTS core.dim_body_type (
    body_type_id integer PRIMARY KEY,
    name         text,
    std_id       integer,
    body_group   text NOT NULL
);
@@
CREATE TABLE IF NOT EXISTS core.fct_price (
    price_id            bigint PRIMARY KEY,
    created_at          timestamp,
    organization_id     integer,
    loading_date        date    NOT NULL,
    end_loading_date    date,
    loading_city_gcid   integer NOT NULL,
    unloading_city_gcid integer NOT NULL,
    distance            double precision NOT NULL,
    total_weight        double precision NOT NULL,
    total_volume        double precision NOT NULL,
    weight_category     varchar(4) NOT NULL,
    volume_category     varchar(4) NOT NULL,
    body_group_primary  text    NOT NULL,
    price_raw           double precision NOT NULL,
    currency_code       varchar(3) NOT NULL,
    fx_rate             double precision NOT NULL,
    price_rub           double precision NOT NULL,
    price_type          smallint NOT NULL,
    is_fact             boolean  NOT NULL,
    complex             boolean  NOT NULL,
    outlier_mark        boolean  NOT NULL,
    loaded_at           timestamptz NOT NULL DEFAULT now()
);
@@
CREATE INDEX IF NOT EXISTS fct_price_loading_date_idx ON core.fct_price (loading_date);
@@
CREATE TABLE IF NOT EXISTS core.fct_price_body_group (
    price_id   bigint NOT NULL REFERENCES core.fct_price (price_id) ON DELETE CASCADE,
    body_group text   NOT NULL,
    PRIMARY KEY (price_id, body_group)
);
@@
CREATE TABLE IF NOT EXISTS core.fct_price_month (
    price_id    bigint NOT NULL REFERENCES core.fct_price (price_id) ON DELETE CASCADE,
    price_date  date   NOT NULL,
    price_month date   NOT NULL,
    PRIMARY KEY (price_id, price_date)
);
@@
CREATE TABLE IF NOT EXISTS core.dq_quarantine_prices (
    price_id          bigint PRIMARY KEY,
    loading_date      date,
    reason_code       text NOT NULL,
    price             double precision,
    currency_code     varchar(3),
    nearest_rate_date date,
    quarantined_at    timestamptz NOT NULL DEFAULT now()
);
@@
CREATE INDEX IF NOT EXISTS dq_quarantine_loading_date_idx ON core.dq_quarantine_prices (loading_date);
@@
CREATE TABLE IF NOT EXISTS mart.route_card (
    month_start         date    NOT NULL,
    loading_city_gcid   integer NOT NULL,
    unloading_city_gcid integer NOT NULL,
    loading_city        text,
    unloading_city      text,
    body_group          text    NOT NULL,
    weight_category     varchar(4) NOT NULL,
    p25_trip            double precision,
    median_trip         double precision,
    p75_trip            double precision,
    avg_trip            double precision,
    p25_km              double precision,
    median_km           double precision,
    p75_km              double precision,
    trips_count         integer NOT NULL,
    carriers_count      integer NOT NULL,
    cv_rate             double precision,
    mom_pct             double precision,
    yoy_pct             double precision,
    reliability_level   text    NOT NULL,
    as_of               date    NOT NULL,
    built_at            timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (month_start, loading_city_gcid, unloading_city_gcid, body_group, weight_category)
);
@@
CREATE INDEX IF NOT EXISTS route_card_route_idx
    ON mart.route_card (loading_city_gcid, unloading_city_gcid, body_group, month_start);
@@
CREATE TABLE IF NOT EXISTS mart.ml_price_predictions (
    price_id            bigint NOT NULL,
    model_name          text   NOT NULL,
    split               text   NOT NULL,
    loading_date        date,
    loading_city_gcid   integer,
    unloading_city_gcid integer,
    body_group          text,
    actual_price_rub    double precision,
    predicted_price_rub double precision NOT NULL,
    abs_error_rub       double precision,
    ape_pct             double precision,
    scored_at           timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (price_id, model_name)
);
@@
CREATE TABLE IF NOT EXISTS mart.ml_model_metrics (
    model_name text NOT NULL,
    as_of      date NOT NULL,
    n_train    integer,
    n_test     integer,
    r2         double precision,
    mape_pct   double precision,
    rmse_rub   double precision,
    mae_rub    double precision,
    trained_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (model_name, as_of)
);
