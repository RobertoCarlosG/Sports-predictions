-- Sports Predictions — esquema NBA: equipos y partidos
-- Ejecutar tras 001-010. Tablas nba_* separadas de MLB (IDs de partido son strings).
-- psql "$DATABASE_URL" -f sql/011_nba_core.sql

CREATE TABLE IF NOT EXISTS nba_teams (
    id INTEGER NOT NULL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    abbreviation VARCHAR(8) NOT NULL,
    conference VARCHAR(16),
    division VARCHAR(32)
);

CREATE TABLE IF NOT EXISTS nba_games (
    game_id VARCHAR(16) NOT NULL PRIMARY KEY,
    season VARCHAR(8) NOT NULL,
    game_date DATE NOT NULL,
    game_datetime_utc TIMESTAMPTZ,
    status VARCHAR(64) NOT NULL,
    home_team_id INTEGER NOT NULL,
    away_team_id INTEGER NOT NULL,
    arena VARCHAR(256),
    home_score INTEGER,
    away_score INTEGER,
    boxscore_json JSONB,
    CONSTRAINT fk_nba_games_home_team FOREIGN KEY (home_team_id) REFERENCES nba_teams (id),
    CONSTRAINT fk_nba_games_away_team FOREIGN KEY (away_team_id) REFERENCES nba_teams (id)
);

CREATE INDEX IF NOT EXISTS idx_nba_games_date ON nba_games (game_date);
CREATE INDEX IF NOT EXISTS idx_nba_games_season ON nba_games (season);
CREATE INDEX IF NOT EXISTS idx_nba_games_home ON nba_games (home_team_id);
CREATE INDEX IF NOT EXISTS idx_nba_games_away ON nba_games (away_team_id);
