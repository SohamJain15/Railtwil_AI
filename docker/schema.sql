CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS stations (id VARCHAR(80) PRIMARY KEY, station_code VARCHAR(20) NOT NULL, name VARCHAR(120) NOT NULL, latitude DOUBLE PRECISION NOT NULL, longitude DOUBLE PRECISION NOT NULL, zone VARCHAR(80) NOT NULL, station_type VARCHAR(40) NOT NULL, source_name VARCHAR(120) NOT NULL, source_type VARCHAR(40) NOT NULL, source_timestamp TIMESTAMPTZ NOT NULL, ingested_at TIMESTAMPTZ NOT NULL, data_quality DOUBLE PRECISION NOT NULL, is_synthetic BOOLEAN NOT NULL, scenario_id VARCHAR(120));
CREATE TABLE IF NOT EXISTS simulation_records (id VARCHAR(80) PRIMARY KEY, record_type VARCHAR(80) NOT NULL, payload JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL);
DO $$ DECLARE table_name TEXT; BEGIN
  FOREACH table_name IN ARRAY ARRAY['tracks','blocks','platforms','junctions','routes','trains','timetables','train_movements','train_states','events','conflicts','simulation_runs','simulation_events','recommendations','what_if_results','safety_checks','metrics','validation_runs','validation_results','validation_reports'] LOOP
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), payload JSONB NOT NULL DEFAULT ''{}'', created_at TIMESTAMPTZ NOT NULL DEFAULT now())', table_name);
  END LOOP;
END $$;
