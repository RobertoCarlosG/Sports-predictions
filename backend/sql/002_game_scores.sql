-- Marcadores persistidos (schedule MLB incluye score en partidos finalizados / en curso)
ALTER TABLE games
  ADD COLUMN IF NOT EXISTS home_score INTEGER,
  ADD COLUMN IF NOT EXISTS away_score INTEGER;
