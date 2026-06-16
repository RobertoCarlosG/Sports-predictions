-- Marca de calidad de datos en la caché de predicciones
-- Ejecutar después de 002_prediction_cache_and_admin.sql

-- TRUE = el vector de features se rellenó con constantes simétricas (sin snapshot o
-- sin historial previo); la probabilidad ~50% no es fiable. El front muestra un aviso.
ALTER TABLE prediction_results
ADD COLUMN IF NOT EXISTS defaults_injected BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN prediction_results.defaults_injected IS 'TRUE si la predicción usó constantes por falta de datos (snapshot ausente o sin historial); la probabilidad no es fiable.';
