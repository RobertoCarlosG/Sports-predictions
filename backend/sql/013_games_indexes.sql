-- Sports Predictions — índices de lectura en `games`.
-- Ejecutar tras 012_nba_features_predictions.sql. Idempotente.
-- psql "$DATABASE_URL" -f sql/013_games_indexes.sql
--
-- `games` solo tenía la PK: GET /games?date=, backtest, historial y el rebuild de
-- snapshots filtraban/ordenaban por fecha con Seq Scan sobre toda la tabla.

-- GET /games?date=…, rebuild (ORDER BY game_date, game_pk), backtest por rango de fechas.
CREATE INDEX IF NOT EXISTS idx_games_game_date ON games (game_date, game_pk);

-- Historial y rebuild por temporada (WHERE season = … ORDER BY game_date).
CREATE INDEX IF NOT EXISTS idx_games_season_game_date ON games (season, game_date);
