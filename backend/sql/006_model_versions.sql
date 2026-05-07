-- Sports Predictions — historial y estado del modelo activo
-- Ejecutar después de las migraciones 001-005.
-- Detalle: docs/migraciones.md.
--
-- Una fila por carga de modelo (lifespan al arrancar, /admin/model/reload, etc.).
-- `is_active = TRUE` apunta al modelo cargado en memoria. Solo una fila puede ser activa
-- a la vez (índice parcial UNIQUE). El histórico permite rollback consciente y auditoría
-- de qué modelo sirvió predicciones en cada momento.

CREATE TABLE IF NOT EXISTS model_versions (
    id                    SERIAL PRIMARY KEY,
    model_version         VARCHAR(80)  NOT NULL,
    base_version          VARCHAR(64)  NOT NULL,
    loaded_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    file_mtime            TIMESTAMPTZ  NULL,
    file_size_bytes       BIGINT       NULL,
    is_synthetic          BOOLEAN      NOT NULL DEFAULT FALSE,
    trained_on_games      INTEGER      NULL,
    val_accuracy_home     DOUBLE PRECISION NULL,
    val_mae_total_runs    DOUBLE PRECISION NULL,
    val_proba_home_std    DOUBLE PRECISION NULL,
    split_mode            VARCHAR(40)  NULL,
    val_from_requested    DATE         NULL,
    feature_names_json    TEXT         NULL,
    loaded_by             VARCHAR(64)  NULL,
    notes                 TEXT         NULL,
    is_active             BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_model_versions_loaded_at
    ON model_versions (loaded_at DESC);

-- Índice parcial UNIQUE: garantiza una sola fila con is_active = TRUE.
-- Postgres permite múltiples filas con FALSE bajo este índice (no contado).
CREATE UNIQUE INDEX IF NOT EXISTS ux_model_versions_active
    ON model_versions (is_active)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_model_versions_base_version
    ON model_versions (base_version);

COMMENT ON TABLE model_versions IS
    'Historial y estado del modelo activo. Una fila por carga (lifespan o /admin/model/reload).';
COMMENT ON COLUMN model_versions.model_version IS
    'Versión completa con sufijo de signatura del archivo, p. ej. "rf-db-v1@a8b3f2c4".';
COMMENT ON COLUMN model_versions.base_version IS
    'Versión "humana" sin sufijo, p. ej. "rf-db-v1" o "rf-synthetic-v0".';
COMMENT ON COLUMN model_versions.is_synthetic IS
    'TRUE si el modelo es el sintético de fallback (base_version empieza por "rf-synthetic").';
COMMENT ON COLUMN model_versions.is_active IS
    'TRUE solo para el modelo cargado en memoria ahora mismo (UNIQUE parcial).';
COMMENT ON COLUMN model_versions.loaded_by IS
    'Usuario admin que disparó /admin/model/reload, o NULL si fue carga automática (lifespan).';
