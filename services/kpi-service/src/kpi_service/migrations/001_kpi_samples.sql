CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS kpi_samples (
    sample_id uuid,
    ts timestamptz NOT NULL,
    site_id text,
    node_id text,
    cell_id text NOT NULL,
    region text,
    dl_throughput_mbps double precision,
    prb_util_pct double precision,
    rrc_setup_success_pct double precision,
    drop_call_rate_pct double precision,
    availability_pct double precision,
    PRIMARY KEY (cell_id, ts)
);

SELECT create_hypertable('kpi_samples', 'ts', if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 day');

CREATE INDEX IF NOT EXISTS idx_kpi_samples_cell_ts_desc ON kpi_samples (cell_id, ts DESC);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz DEFAULT now()
);
