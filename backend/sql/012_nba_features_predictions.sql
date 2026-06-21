-- Sports Predictions — esquema NBA: feature store y caché de predicciones
-- Ejecutar tras 011_nba_core.sql.
-- psql "$DATABASE_URL" -f sql/012_nba_features_predictions.sql

CREATE TABLE IF NOT EXISTS nba_game_feature_snapshots (
    id SERIAL PRIMARY KEY,
    game_id VARCHAR(16) NOT NULL UNIQUE REFERENCES nba_games (game_id) ON DELETE CASCADE,
    home_win_pct_roll DOUBLE PRECISION,
    away_win_pct_roll DOUBLE PRECISION,
    home_pts_for_roll DOUBLE PRECISION,
    away_pts_for_roll DOUBLE PRECISION,
    home_pts_against_roll DOUBLE PRECISION,
    away_pts_against_roll DOUBLE PRECISION,
    home_net_rating_roll DOUBLE PRECISION,
    away_net_rating_roll DOUBLE PRECISION,
    home_pace_roll DOUBLE PRECISION,
    away_pace_roll DOUBLE PRECISION,
    home_efg_roll DOUBLE PRECISION,
    away_efg_roll DOUBLE PRECISION,
    home_rest_days INTEGER,
    away_rest_days INTEGER,
    home_is_b2b INTEGER,
    away_is_b2b INTEGER,
    home_win INTEGER,
    margin DOUBLE PRECISION,
    total_points DOUBLE PRECISION,
    feature_vector_json TEXT
);

CREATE TABLE IF NOT EXISTS nba_prediction_results (
    game_id VARCHAR(16) NOT NULL PRIMARY KEY REFERENCES nba_games (game_id) ON DELETE CASCADE,
    home_win_probability DOUBLE PRECISION NOT NULL,
    margin_estimate DOUBLE PRECISION NOT NULL,
    total_points_estimate DOUBLE PRECISION NOT NULL,
    spread_line DOUBLE PRECISION NOT NULL,
    over_under_line DOUBLE PRECISION NOT NULL,
    over_probability DOUBLE PRECISION,
    model_version VARCHAR(64) NOT NULL,
    defaults_injected BOOLEAN NOT NULL DEFAULT FALSE,
    trigger_reason VARCHAR(64),
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    predicted_winner VARCHAR(10),
    actual_winner VARCHAR(10),
    is_correct BOOLEAN,
    evaluated_at TIMESTAMPTZ
);
