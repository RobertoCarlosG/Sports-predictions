-- Liga (AL/NL) y división por equipo, para segmentar partidos y apuestas.
-- Ejecutar después de las migraciones anteriores.

ALTER TABLE teams
  ADD COLUMN IF NOT EXISTS league VARCHAR(32),
  ADD COLUMN IF NOT EXISTS division VARCHAR(32);

-- Backfill de los 30 equipos activos (afiliación estática).
-- AL East
UPDATE teams SET league = 'AL', division = 'AL East'    WHERE id IN (110, 111, 139, 141, 147);
-- AL Central
UPDATE teams SET league = 'AL', division = 'AL Central' WHERE id IN (114, 116, 118, 142, 145);
-- AL West
UPDATE teams SET league = 'AL', division = 'AL West'    WHERE id IN (108, 117, 133, 136, 140);
-- NL East
UPDATE teams SET league = 'NL', division = 'NL East'    WHERE id IN (120, 121, 143, 144, 146);
-- NL Central
UPDATE teams SET league = 'NL', division = 'NL Central' WHERE id IN (112, 113, 134, 138, 158);
-- NL West
UPDATE teams SET league = 'NL', division = 'NL West'    WHERE id IN (109, 115, 119, 135, 137);

-- Índices para filtrar partidos por liga/división.
CREATE INDEX IF NOT EXISTS idx_teams_league ON teams (league) WHERE league IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_teams_division ON teams (division) WHERE division IS NOT NULL;

COMMENT ON COLUMN teams.league IS 'Liga MLB: "AL" (Americana) o "NL" (Nacional)';
COMMENT ON COLUMN teams.division IS 'División: "AL East", "AL Central", "AL West", "NL East", "NL Central", "NL West"';
