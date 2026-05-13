-- Sports Predictions — usuarios app (Google OAuth) + control de apuestas
-- Ejecutar después de 006_model_versions.sql (requiere `games` existente).
-- `gen_random_uuid()` requiere extensión pgcrypto (habitual en Supabase).

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS app_users (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    google_id VARCHAR(128) NOT NULL UNIQUE,
    email VARCHAR(256) NOT NULL UNIQUE,
    display_name VARCHAR(256),
    picture_url TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_app_users_google_id ON app_users (google_id);

CREATE TABLE IF NOT EXISTS bet_banks (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES app_users (id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    initial_amount DOUBLE PRECISION NOT NULL,
    currency VARCHAR(8) NOT NULL DEFAULT 'USD',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bet_banks_user_id ON bet_banks (user_id);

CREATE TABLE IF NOT EXISTS bet_periods (
    id SERIAL PRIMARY KEY,
    bank_id INTEGER NOT NULL REFERENCES bet_banks (id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES app_users (id) ON DELETE CASCADE,
    name VARCHAR(64) NOT NULL,
    year INTEGER NOT NULL CHECK (year >= 2000 AND year <= 2100),
    month INTEGER NOT NULL CHECK (month >= 1 AND month <= 12),
    starting_balance DOUBLE PRECISION NOT NULL,
    closing_balance DOUBLE PRECISION,
    status VARCHAR(16) NOT NULL DEFAULT 'open',
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ux_bet_periods_bank_year_month UNIQUE (bank_id, year, month)
);

CREATE INDEX IF NOT EXISTS idx_bet_periods_user_bank ON bet_periods (user_id, bank_id);
CREATE INDEX IF NOT EXISTS idx_bet_periods_status ON bet_periods (status);

CREATE TABLE IF NOT EXISTS bets (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES app_users (id) ON DELETE CASCADE,
    bank_id INTEGER NOT NULL REFERENCES bet_banks (id) ON DELETE CASCADE,
    period_id INTEGER NOT NULL REFERENCES bet_periods (id) ON DELETE RESTRICT,
    game_pk INTEGER NOT NULL REFERENCES games (game_pk) ON DELETE RESTRICT,
    bet_type VARCHAR(16) NOT NULL CHECK (bet_type IN ('moneyline', 'over_under')),
    bet_side VARCHAR(16) NOT NULL,
    stake DOUBLE PRECISION NOT NULL CHECK (stake > 0),
    odds DOUBLE PRECISION NOT NULL CHECK (odds >= 1.0),
    ou_line DOUBLE PRECISION,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    result_source VARCHAR(16),
    result_checked_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_bets_status CHECK (
        status IN ('pending', 'won', 'lost', 'push', 'cancelled')
    ),
    CONSTRAINT chk_bets_result_source CHECK (
        result_source IS NULL OR result_source IN ('local', 'mlb_api', 'manual')
    )
);

CREATE INDEX IF NOT EXISTS idx_bets_user_id ON bets (user_id);
CREATE INDEX IF NOT EXISTS idx_bets_bank_period ON bets (bank_id, period_id);
CREATE INDEX IF NOT EXISTS idx_bets_game_pk ON bets (game_pk);
CREATE INDEX IF NOT EXISTS idx_bets_status ON bets (status);

COMMENT ON TABLE app_users IS 'Usuarios finales (OAuth Google) para control de apuestas; distintos de admin_users.';
COMMENT ON TABLE bet_banks IS 'Bancos / bankroll por usuario.';
COMMENT ON TABLE bet_periods IS 'Corte mensual por banco (saldo apertura/cierre).';
COMMENT ON TABLE bets IS 'Apuestas registradas (MoneyLine u Over/Under).';
COMMENT ON COLUMN bets.ou_line IS 'Línea O/U explícita del usuario; NULL si no aplica (MoneyLine).';
COMMENT ON COLUMN bets.result_source IS 'Origen del marcador usado para resolver: local, mlb_api o manual.';
