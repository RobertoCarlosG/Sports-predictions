-- Sports Predictions — caché de inferencia + operadores administrativos
-- Ejecutar después de 001_initial_schema.sql (Supabase SQL Editor o psql).

-- Resultados de estimación precalculados (Fase 5 pipeline). Una fila por partido.
CREATE TABLE IF NOT EXISTS prediction_results (
    game_pk INTEGER NOT NULL PRIMARY KEY REFERENCES games (game_pk) ON DELETE CASCADE,
    home_win_probability DOUBLE PRECISION NOT NULL,
    total_runs_estimate DOUBLE PRECISION NOT NULL,
    over_under_line DOUBLE PRECISION NOT NULL,
    model_version VARCHAR(64) NOT NULL,
    trigger_reason VARCHAR(64) NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prediction_results_computed_at ON prediction_results (computed_at);
CREATE INDEX IF NOT EXISTS idx_prediction_results_model_version ON prediction_results (model_version);

-- Usuarios con acceso al panel de operaciones (entrenamiento manual, caché, etc.)
CREATE TABLE IF NOT EXISTS admin_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_users_username ON admin_users (username);
