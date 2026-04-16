-- Sports Predictions — esquema inicial (MLB)
-- Ejecutar en Supabase: SQL Editor → New query → pegar → Run
-- O: psql "$DATABASE_URL" -f sql/001_initial_schema.sql

-- Extensión útil en Postgres (opcional; Supabase suele tenerla)
-- CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER NOT NULL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    abbreviation VARCHAR(8) NOT NULL,
    venue_id INTEGER,
    venue_name VARCHAR(256)
);

CREATE TABLE IF NOT EXISTS games (
    game_pk INTEGER NOT NULL PRIMARY KEY,
    season VARCHAR(8) NOT NULL,
    game_date DATE NOT NULL,
    game_datetime_utc TIMESTAMPTZ,
    status VARCHAR(64) NOT NULL,
    home_team_id INTEGER NOT NULL,
    away_team_id INTEGER NOT NULL,
    venue_id INTEGER,
    venue_name VARCHAR(256),
    home_score INTEGER,
    away_score INTEGER,
    lineups_json JSONB,
    boxscore_json JSONB,
    CONSTRAINT fk_games_home_team FOREIGN KEY (home_team_id) REFERENCES teams (id),
    CONSTRAINT fk_games_away_team FOREIGN KEY (away_team_id) REFERENCES teams (id)
);

CREATE TABLE IF NOT EXISTS game_weather (
    id SERIAL PRIMARY KEY,
    game_pk INTEGER NOT NULL UNIQUE REFERENCES games (game_pk) ON DELETE CASCADE,
    temperature_c DOUBLE PRECISION,
    humidity_pct DOUBLE PRECISION,
    wind_speed_mps DOUBLE PRECISION,
    pressure_mbar DOUBLE PRECISION,
    elevation_m DOUBLE PRECISION,
    raw_json JSONB,
    fetched_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS game_feature_snapshots (
    id SERIAL PRIMARY KEY,
    game_pk INTEGER NOT NULL UNIQUE REFERENCES games (game_pk) ON DELETE CASCADE,
    home_wins_roll DOUBLE PRECISION,
    away_wins_roll DOUBLE PRECISION,
    home_runs_avg_roll DOUBLE PRECISION,
    away_runs_avg_roll DOUBLE PRECISION,
    temperature_c DOUBLE PRECISION,
    humidity_pct DOUBLE PRECISION,
    wind_speed_mps DOUBLE PRECISION,
    elevation_m DOUBLE PRECISION,
    home_win INTEGER,
    total_runs DOUBLE PRECISION,
    feature_vector_json TEXT
);
