-- Optimización de tabla teams para reducir lock contention
-- Ejecutar después de las migraciones anteriores

-- Índice para optimizar búsquedas por team_id en operaciones concurrentes
-- (El índice PK ya existe, pero añadimos índices adicionales si hay JOINs frecuentes)

-- Índice para venue_id si se hacen búsquedas frecuentes por venue
CREATE INDEX IF NOT EXISTS idx_teams_venue_id ON teams (venue_id) WHERE venue_id IS NOT NULL;

-- Comentarios para documentar
COMMENT ON TABLE teams IS 'Equipos de MLB. Se actualiza frecuentemente durante sincronización de partidos.';
COMMENT ON COLUMN teams.venue_id IS 'ID del estadio/venue del equipo';
COMMENT ON COLUMN teams.venue_name IS 'Nombre del estadio/venue del equipo';

-- Opcional: Ajustar autovacuum para tabla teams si hay alta concurrencia
-- Descomenta si continúan los problemas de lock contention:
-- ALTER TABLE teams SET (
--   autovacuum_vacuum_scale_factor = 0.05,
--   autovacuum_analyze_scale_factor = 0.02
-- );
