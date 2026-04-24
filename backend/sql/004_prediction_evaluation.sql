-- Añadir campos para evaluación de predicciones
-- Ejecutar después de 002_prediction_cache_and_admin.sql

-- Añadir campos para tracking de aciertos/fallos
ALTER TABLE prediction_results
ADD COLUMN IF NOT EXISTS predicted_winner VARCHAR(10) NULL,
ADD COLUMN IF NOT EXISTS actual_winner VARCHAR(10) NULL,
ADD COLUMN IF NOT EXISTS is_correct BOOLEAN NULL,
ADD COLUMN IF NOT EXISTS evaluated_at TIMESTAMPTZ NULL;

-- Índices para queries de métricas
CREATE INDEX IF NOT EXISTS idx_prediction_results_is_correct ON prediction_results (is_correct) WHERE is_correct IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_prediction_results_evaluated_at ON prediction_results (evaluated_at) WHERE evaluated_at IS NOT NULL;

-- Comentarios
COMMENT ON COLUMN prediction_results.predicted_winner IS 'Ganador predicho por el modelo: home o away';
COMMENT ON COLUMN prediction_results.actual_winner IS 'Ganador real del juego: home, away, o tie';
COMMENT ON COLUMN prediction_results.is_correct IS 'TRUE si la predicción fue correcta, FALSE si falló, NULL si no se ha evaluado';
COMMENT ON COLUMN prediction_results.evaluated_at IS 'Timestamp de cuándo se evaluó la predicción contra el resultado real';
