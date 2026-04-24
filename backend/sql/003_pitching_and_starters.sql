-- Abridores, ERA en snapshots y caché de ERA (MLB API). Aplicar en la misma base que 001/002.
-- Incluye comentario: home_bullpen_era/away = ERA del pitcheo colectivo del equipo (no solo relevistas).

ALTER TABLE games
  ADD COLUMN IF NOT EXISTS home_starter_id INTEGER NULL,
  ADD COLUMN IF NOT EXISTS away_starter_id INTEGER NULL;

ALTER TABLE game_feature_snapshots
  ADD COLUMN IF NOT EXISTS home_starter_era DOUBLE PRECISION NULL,
  ADD COLUMN IF NOT EXISTS away_starter_era DOUBLE PRECISION NULL,
  ADD COLUMN IF NOT EXISTS home_bullpen_era DOUBLE PRECISION NULL,
  ADD COLUMN IF NOT EXISTS away_bullpen_era DOUBLE PRECISION NULL;

CREATE TABLE IF NOT EXISTS pitching_era_cache (
  id            SERIAL PRIMARY KEY,
  kind          VARCHAR(1) NOT NULL CHECK (kind IN ('P', 'T')),
  ref_id        INTEGER NOT NULL,
  season        VARCHAR(8) NOT NULL,
  era           DOUBLE PRECISION NOT NULL,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT ux_pitching_era_cache UNIQUE (kind, ref_id, season)
);

COMMENT ON TABLE pitching_era_cache IS 'Caché de ERA (jugador o equipo) por temporada, para rebuild sin reconsultar la API.';
COMMENT ON COLUMN game_feature_snapshots.home_bullpen_era IS
  'Proxy: ERA pitcheo colectivo del equipo (API /teams/…/stats, incluye abridor).';
