# Migraciones SQL — Sports-Predictions

**Última actualización:** 7 de mayo de 2026.

Sports-Predictions **no usa Alembic**. Las migraciones son archivos `.sql` versionados en [`backend/sql/`](../backend/sql/) que se aplican manualmente, en orden, en el SQL Editor de Supabase o con `psql` contra `DATABASE_URL`.

Este documento es la fuente de verdad para:

- Saber **en qué orden** ejecutar las migraciones.
- Saber **qué cambia** cada una y **de qué depende**.
- Diagnosticar errores típicos (`admin_users` no existe, faltan columnas, login devuelve 503, etc.).

> Para la referencia humana del esquema (todas las tablas y columnas en un solo lugar), ver [`backend/sql/schema.txt`](../backend/sql/schema.txt).

---

## 1. Resumen rápido

| Orden | Archivo | Qué hace | Idempotente |
|-------|---------|----------|-------------|
| 1 | `001_initial_schema.sql` | Crea `teams`, `games`, `game_weather`, `game_feature_snapshots`. | ✅ (`IF NOT EXISTS`) |
| 2 | `002_game_scores.sql` | Añade `home_score`, `away_score` a `games`. | ✅ |
| 3 | `002_prediction_cache_and_admin.sql` | Crea `prediction_results` y `admin_users`. | ✅ |
| 4 | `003_pitching_and_starters.sql` | Añade `home/away_starter_id`, ERAs en snapshots, crea `pitching_era_cache`. | ✅ |
| 5 | `004_prediction_evaluation.sql` | Añade `predicted_winner`, `actual_winner`, `is_correct`, `evaluated_at` a `prediction_results`. | ✅ |
| 6 | `005_teams_optimization.sql` | Índice `venue_id` en `teams`, comentarios de tabla. | ✅ |
| 7 | `006_model_versions.sql` | Tabla `model_versions` con histórico y flag `is_active` único. | ✅ |

Aunque dos archivos comparten el prefijo `002_`, **ambos deben aplicarse** y en este orden:

```bash
backend/sql/001_initial_schema.sql
backend/sql/002_game_scores.sql
backend/sql/002_prediction_cache_and_admin.sql
backend/sql/003_pitching_and_starters.sql
backend/sql/004_prediction_evaluation.sql
backend/sql/005_teams_optimization.sql
backend/sql/006_model_versions.sql
```

> **¿Por qué dos `002_`?** `002_game_scores.sql` evolucionó la tabla `games`, mientras que `002_prediction_cache_and_admin.sql` introdujo dos nuevas tablas. Se mantienen como migraciones independientes para reflejar la historia real. Próximo número libre: **`007_`**.

---

## 2. Detalle por archivo

### 2.1 `001_initial_schema.sql` — esquema base

**Crea:** `teams`, `games`, `game_weather`, `game_feature_snapshots`.

- `teams.id` no es `SERIAL`: se usa el id real de `statsapi.mlb.com`.
- `games.game_pk` PK; FKs a `teams.id` por home/away.
- `game_weather` y `game_feature_snapshots` con `game_pk UNIQUE` y `ON DELETE CASCADE`.

**Notas:** los campos `lineups_json`, `boxscore_json` son `JSONB` y aceptan `NULL`. `home_score` / `away_score` se añadieron en `002_game_scores.sql` para migraciones tempranas; bases nuevas pueden tener ya estas columnas si se aplica `002` después.

### 2.2 `002_game_scores.sql` — marcadores

```sql
ALTER TABLE games
  ADD COLUMN IF NOT EXISTS home_score INTEGER,
  ADD COLUMN IF NOT EXISTS away_score INTEGER;
```

Necesario para que la sincronización persista los marcadores recibidos del schedule MLB en partidos finalizados o en curso.

### 2.3 `002_prediction_cache_and_admin.sql` — caché de inferencia + admin

**Crea:**

- `prediction_results` (PK `game_pk`, FK a `games.game_pk` con `ON DELETE CASCADE`): caché de inferencia con `model_version`, `trigger_reason`, `computed_at`. Índices por `computed_at` y `model_version`.
- `admin_users` (id, username UNIQUE, password_hash bcrypt, is_active, created_at). Índice por `username`.

**No inserta filas** en `admin_users`: el alta del primer operador se hace por:

- CLI `create-admin` (recomendado): `cd backend && create-admin --username … --password '…'` (tras `pip install -e ".[dev]"`).
- Bootstrap HTTP, una vez: `POST /api/v1/admin/auth/bootstrap` con header `X-Admin-Bootstrap-Secret` (requiere `ADMIN_BOOTSTRAP_SECRET` y `ADMIN_JWT_SECRET` en `.env`; quitar el secret de bootstrap después).

**Síntoma si falta esta migración:** `POST /api/v1/admin/auth/login` responde **503** con detalle "Falta la tabla admin_users…". El backend tiene un endpoint público `GET /api/v1/admin/auth/ready` que ya advierte de esto.

### 2.4 `003_pitching_and_starters.sql` — abridores y ERAs

**Modifica:** `games` (añade `home_starter_id`, `away_starter_id`), `game_feature_snapshots` (añade `home/away_starter_era`, `home/away_bullpen_era`).

**Crea:** `pitching_era_cache` con `UNIQUE (kind, ref_id, season)` (kind `P` = jugador, `T` = staff de equipo).

**Comentarios** (`COMMENT ON COLUMN`): `home_bullpen_era` no es solo bullpen, es **ERA del staff completo** (incluye abridor) por simplicidad de la API `/teams/{id}/stats`. Se mantiene el nombre por compatibilidad.

**Síntoma si falta:** `feature_snapshots.py` rellena los ERAs con `DEFAULT_ERA` / `DEFAULT_STAFF_ERA` y marca `defaults_injected = 1`; el modelo entrena pero con menos señal.

### 2.5 `004_prediction_evaluation.sql` — evaluación de aciertos

**Modifica `prediction_results`:**

- `predicted_winner VARCHAR(10)` — `"home"` o `"away"`.
- `actual_winner VARCHAR(10)` — `"home"`, `"away"` o `"tie"`.
- `is_correct BOOLEAN`.
- `evaluated_at TIMESTAMPTZ`.

**Índices** (parciales, para queries de métricas):

- `idx_prediction_results_is_correct` `WHERE is_correct IS NOT NULL`.
- `idx_prediction_results_evaluated_at` `WHERE evaluated_at IS NOT NULL`.

**Comentarios** explicativos por columna.

**Síntoma si falta:** los endpoints `/admin/predictions/metrics`, `/predictions/evaluations`, `/predictions/backtest` fallan con `column ... does not exist`. El frontend muestra error 500 en la pestaña Dashboard.

### 2.6 `005_teams_optimization.sql` — anti-lock contention

**Crea** índice parcial `idx_teams_venue_id ON teams (venue_id) WHERE venue_id IS NOT NULL` y comentarios de tabla.

**Opcional comentado:** ajuste de autovacuum para `teams` (descomentar si hay alta concurrencia y siguen apareciendo timeouts en `UPDATE teams …`).

**Por qué existe:** durante la sincronización de partidos, varios syncs paralelos podían pisarse al hacer `UPDATE teams SET venue_id=… WHERE id=…` y disparar `QueryCanceledError` por `statement_timeout`. La solución principal vino del lado del código (en `mlb_sync.py`: solo actualizar si hay cambios reales + `flush()` explícito); este índice es complementario.

### 2.7 `006_model_versions.sql` — historial y modelo activo

**Crea** `model_versions` con:

- Identificación del modelo: `model_version` (con sufijo `@<mtime_ns_hex>`), `base_version` (sin sufijo), `is_synthetic`.
- Metadata de archivo: `file_mtime`, `file_size_bytes`.
- Métricas de entrenamiento (cuando `train_from_db` las dejó en el bundle): `trained_on_games`, `val_accuracy_home`, `val_mae_total_runs`, `val_proba_home_std`, `split_mode`, `val_from_requested`, `feature_names_json`.
- Auditoría: `loaded_at`, `loaded_by` (admin que recargó), `notes`.
- Flag `is_active` con índice parcial UNIQUE → solo una fila puede ser TRUE a la vez.

**Insertan filas:**

- `lifespan` al arrancar (`loaded_by = NULL`, `notes = "lifespan startup"`).
- `POST /admin/model/reload` (`loaded_by = username`, `notes = "manual reload"`).

**Síntoma si falta:** el backend arranca, pero `app.services.model_registry.record_model_load` loguea un warning ("¿migración 006 aplicada?") y `GET /api/v1/model/info` devuelve `model_loaded=false`. El modelo en memoria sigue funcionando; solo se pierde la trazabilidad.

---

## 3. Aplicación recomendada

### 3.1 En Supabase (UI)

1. Abre tu proyecto → **SQL** → **New query**.
2. Copia el contenido del primer `.sql`, ejecuta. Comprueba en **Tables** que aparecen.
3. Repite para el siguiente archivo, **en orden**.
4. Tras `002_prediction_cache_and_admin.sql`, configura `ADMIN_JWT_SECRET` en el backend y crea el primer operador.

### 3.2 Con `psql` contra `DATABASE_URL`

```bash
cd backend
for f in sql/001_initial_schema.sql \
         sql/002_game_scores.sql \
         sql/002_prediction_cache_and_admin.sql \
         sql/003_pitching_and_starters.sql \
         sql/004_prediction_evaluation.sql \
         sql/005_teams_optimization.sql \
         sql/006_model_versions.sql; do
  echo ">>> $f"
  psql "$DATABASE_URL" -f "$f"
done
```

Todas las migraciones son **idempotentes** (`IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`), así que repetirlas no rompe nada.

### 3.3 Verificación rápida

```sql
-- Tablas esperadas
SELECT table_name FROM information_schema.tables
WHERE table_schema='public'
  AND table_name IN (
    'teams', 'games', 'game_weather', 'game_feature_snapshots',
    'pitching_era_cache', 'prediction_results', 'admin_users', 'model_versions'
  );

-- Columnas críticas
SELECT column_name FROM information_schema.columns
WHERE table_name='prediction_results'
  AND column_name IN ('predicted_winner','actual_winner','is_correct','evaluated_at');
```

Y en el API:

```bash
curl https://tu-api/api/v1/admin/auth/ready
# → login_available: true significa JWT secret + admin_users OK.
```

---

## 4. Convenciones para nuevas migraciones

1. **Nombre:** `<NN>_<descripcion-corta>.sql`. Próximo número libre: `007_`.
2. **Idempotentes**: usar `IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`. Tras un fallo a mitad, debe poder reaplicarse limpio.
3. **Sin `DROP` destructivo** sin coordinación previa.
4. **Comentarios SQL** (`COMMENT ON …`) para columnas no obvias.
5. **Actualizar al mismo tiempo:**
   - [`backend/sql/schema.txt`](../backend/sql/schema.txt) (referencia humana).
   - [`backend/sql/README.md`](../backend/sql/README.md) (orden y notas operativas).
   - **Este documento** (`migraciones.md`).
6. Si la migración crea o modifica modelos SQLAlchemy, sincronizar `backend/src/app/models/mlb.py` en el mismo PR.
7. Probar localmente contra una BD vacía siguiendo la lista del paso 3.2.

---

## 5. Migraciones planeadas (no creadas todavía)

Estas se documentan aquí para que cualquiera que abra una migración nueva sepa qué huecos están reservados.

| Próxima | Propuesta | Notas |
|---------|-----------|-------|
| `007_*` | (libre) | — |

---

## 6. Troubleshooting

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| `POST /admin/auth/login` → 503 "Falta la tabla admin_users" | `002_prediction_cache_and_admin.sql` no aplicado en la base apuntada por `DATABASE_URL`. | Aplicar la migración. Verificar que `DATABASE_URL` del API es la misma que la de tu UI Supabase. |
| `column "predicted_winner" does not exist` en `/admin/predictions/metrics` | `004_prediction_evaluation.sql` no aplicado. | Aplicar. |
| `QueryCanceledError: statement timeout` en `UPDATE teams` | Lock contention; si persiste tras `005_teams_optimization.sql`, descomentar el bloque de autovacuum. | Aplicar `005`. Ajustar `DATABASE_STATEMENT_TIMEOUT_SECONDS` si hace falta. |
| `column "home_starter_era" does not exist` en `rebuild_feature_snapshots` | `003_pitching_and_starters.sql` no aplicado. | Aplicar. |
| Backfill ok pero predicciones planas (P(home) ≈ 0.5) | `game_feature_snapshots` está vacío para esos partidos. | Botón **Recalcular indicadores** en `/operations` o `python -m app.cli.rebuild_feature_snapshots --season 2026 --window 10`. |
