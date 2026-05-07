# Visión, contexto y alcance implementado

**Última actualización:** 7 de mayo de 2026 — alineada con `main` (verificado contra `backend/src/app/` y `frontend/src/app/`).

## Qué es Sports-Predictions

**Sports-Predictions** es un monorepo con **dashboard Angular + API FastAPI** para análisis deportivo. El **MVP-1** se centra en **MLB** (datos oficiales vía `statsapi.mlb.com`), con clima de estadio (Open-Meteo) y un modelo de predicción (Random Forest serializado como `joblib`). La arquitectura permite extender a otros deportes (fútbol, NBA) en MVP-2 reutilizando el backend.

**Objetivo de producto (MVP-1):**

- Ver partidos por fecha (Hoy / Mañana / Semana / Historial), con **probabilidad de victoria local**, **carreras estimadas** y **línea O/U**.
- Mostrar el **resultado real** del partido, evaluar el acierto/fallo de la predicción y exponer **métricas agregadas** (accuracy global, backtest por rango).
- Operar el ciclo de vida del producto desde un **panel `/operations`** privado: importar histórico, recalcular indicadores, entrenar modelos contra la BD, recargar sin reiniciar el API.

**No es (todavía):**

- Plataforma multi-usuario con login público, favoritos o apuestas.
- Canal en tiempo real (no hay WebSocket).
- Multi-deporte real: la UI de fútbol/NBA está en `coming-soon`.

## Contexto técnico

| Capa | Tecnología |
|------|------------|
| API | **FastAPI**, SQLAlchemy 2 **async**, **httpx** compartido, rate-limit por IP en memoria |
| Auth (admin) | **JWT HS256** firmado en backend, cookie `HttpOnly` con `SameSite` configurable; rate-limit por IP en `/auth/login` |
| Base de datos | **PostgreSQL**; DDL versionado en `backend/sql/00*.sql` (**sin Alembic**: ver [migraciones.md](migraciones.md)) |
| Cliente web | **Angular** (SPA standalone), Material, signals/computed, caché HTTP con `shareReplay` + TTL |
| ML | `joblib` + `scikit-learn` (Random Forest); training meta embebido en el bundle |
| Despliegue típico | **Supabase** (Postgres) + **Render** (API) + **Vercel** (estático) — ver [deploy.md](deploy.md) |

## Lo implementado en `main` (resumen ejecutivo)

### Backend público (`/api/v1`)

- **Salud / metadatos:** `GET /`, `GET /health`.
- **Modelo activo:** `GET /model/info` (versión, base, `is_synthetic`, `loaded_at`).
- **Partidos:** `GET /games?date=…&sync=…&fetch_details=…&include_predictions=…`, `GET /games/{game_pk}?include_predictions=…`, `POST /games/{game_pk}/weather`.
- **MLB equipos / historial / sync:** `GET /mlb/teams`, `GET /mlb/history/games`, `GET /mlb/history/games/{pk}`, `POST /mlb/sync-range` (≤ 7 días por petición), `POST /mlb/games/{pk}/sync`.
- **Predicción:** `GET /predict/{pk}` (lee caché por `model_version`; calcula y guarda si no existe), `POST /predict/{pk}/refresh` (recalcula y guarda).

### Backend admin (`/api/v1/admin/*`, requiere JWT)

- **Auth:** `GET /auth/ready`, `POST /auth/bootstrap` (primer usuario, una vez), `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me`.
- **Pipeline / ETL:** `POST /pipeline/mlb-daily-snapshot`, `POST /pipeline/rebuild-snapshots`, `POST /pipeline/clear-prediction-cache`, `POST /pipeline/backfill` (segundo plano con tracking), `GET /pipeline/backfill-status`, `POST /pipeline/train`.
- **Modelo:** `POST /model/reload`, `GET /status`.
- **Predicciones:** `POST /predictions/evaluate-pending`, `POST /predictions/recompute-ml-evaluations`, `GET /predictions/metrics`, `GET /predictions/evaluations`, `GET /predictions/backtest`.
- **Modelo (admin):** `GET /admin/model/versions` (histórico con métricas, `loaded_by`, `is_active`).

### Pipeline de datos y ML

- **Ingesta MLB** (`services/mlb_sync.py`): schedule + boxscore + linescore + live feed. Si el live feed falla (típico en partidos finalizados), las alineaciones se derivan del boxscore (`lineups_from_boxscore`). Throttling global con `mlb_throttle.py` y `SET LOCAL statement_timeout` defensivo en escrituras pesadas.
- **Clima**: `services/weather_open_meteo.py` + `data/mlb_stadiums.json`, persistido en `game_weather`.
- **Snapshots de features** (`services/feature_snapshots.py`): rolling window de victorias/runs por equipo (orden cronológico global), ERA real de abridor y staff (`services/pitching_stats.py`), clima, y etiquetas (`home_win`, `total_runs`) en partidos finales. Caché en `pitching_era_cache` para no reconsultar la API.
- **Entrenamiento real desde BD** (`ml/train_from_db.py`): lee `game_feature_snapshots` con etiquetas no nulas, partición temporal (`--val-from` o 80/20 por fecha), entrena `RandomForestClassifier` + `RandomForestRegressor`, calcula validación (accuracy, MAE, std de probabilidad), serializa en joblib con `training_meta` (json) embebido.
- **Inferencia** (`ml/predictor.py`): carga el bundle, alinea el vector a `n_features_in_` del bosque (compatibilidad hacia atrás con modelos viejos de 8/12 columnas), versión expuesta como `<base_version>@<mtime_ns_hex>` para distinguir archivos.
- **Caché de predicciones** (`services/prediction_cache.py` + tabla `prediction_results`): se sirve cuando `model_version` coincide; en `_compute_or_cache_prediction` no se predice partidos pasados sin caché previa.
- **Evaluación automática**: tras `sync_games_for_date`, los partidos finales con caché se evalúan (`predicted_winner`, `actual_winner`, `is_correct`, `evaluated_at`).
- **Job ETL diario** (`services/mlb_daily_snapshot.py`): `daily_snapshot_loop_forever` opt-in con `MLB_DAILY_SNAPSHOT_ENABLED=true`. Importa hoy+mañana (UTC), recalcula snapshots de la temporada actual y deja el modelo activo listo para predecir. Reutilizable bajo demanda desde el panel.

### Frontend (`/`, Angular standalone)

- Rutas: `/mlb/today`, `/mlb/tomorrow`, `/mlb/week`, `/mlb/history`, `/mlb/game/:gamePk`, `/operations`, `/soccer` y `/nba` (estos dos en `coming-soon`).
- **Listado por fecha** con signals + computed, caché por rango y por servicio.
- **Detalle de partido**: marcador, clima, predicción con badge Hit/Miss, box score legible (R/H/E + innings) + JSON, alineaciones. Botones «Actualizar clima» y «Actualizar desde MLB».
- **Historial MLB** con filtros, listado y enlace a detalle.
- **Operaciones**: tabs **Dashboard de rendimiento** (backtest con summary, serie temporal, filas ML+O/U) y **Sincronización y modelos** (sync rápida del día, ETL completo hoy+mañana, backfill por fechas con barra de progreso, recálculo de indicadores, entrenamiento, recargar modelo, vaciar caché). Login JWT con renovación automática durante operaciones largas.

### Tests (`backend/tests/`)

`pytest` con `pytest-asyncio`. Cobertura actual: salud, parse MLB, sync MLB, predictor (incluyendo recarga al cambiar el archivo), feature snapshots, prediction cache (helper), backtest, configuración y URL de BD. **Pendientes**: routes admin/auth, scheduler diario, train_from_db (ver [proximos-pasos.md](proximos-pasos.md) y [estado-real-mvp1.md](estado-real-mvp1.md)).

## No implementado en MVP-1 (referencias)

- Auth pública en el dashboard, otros deportes, re-entrenamiento automático con drift detection, cron real fuera del proceso, particionamiento por temporada, observabilidad (Sentry/Prometheus), CI/CD. Ver [proximos-pasos.md](proximos-pasos.md), [pendientes.md](pendientes.md) y [estado-real-mvp1.md](estado-real-mvp1.md).

Para el detalle de rutas, esquemas, contratos y checklist local, continuar en [estatus-actual.md](estatus-actual.md). Para la auditoría honesta de gaps, ver [estado-real-mvp1.md](estado-real-mvp1.md).
