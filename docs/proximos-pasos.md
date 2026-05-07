# Próximos pasos — roadmap operativo

**Última actualización:** 7 de mayo de 2026.

Este documento es la lista priorizada de **acciones técnicas** para cerrar el MVP-1 y abrir el MVP-2. Para el detalle del estado actual ver [estatus-actual.md](estatus-actual.md). Para los **pendientes de producto** (decisiones abiertas), ver [pendientes.md](pendientes.md). Para la auditoría honesta del repo, ver [estado-real-mvp1.md](estado-real-mvp1.md).

---

## Cierre del MVP-1 — PRs en curso o cercanos

El MVP-1 se cierra en **tres PRs** acordados:

### PR1 — Documentación + migraciones (en curso)

- [x] Reescribir `vision-y-alcance.md`, `estatus-actual.md`, `pendientes.md`, `pendientes-sync-boxscore.md`, `Comportamiento-predicciones.md` con la realidad del código.
- [x] Marcar etapas A-D en `diseno-pipeline-predicciones.md`.
- [x] Crear `proximos-pasos.md` (este archivo).
- [x] Crear [`migraciones.md`](migraciones.md) con detalle de cada `00*_*.sql`, dependencias y troubleshooting.
- [x] Sincronizar [`backend/sql/README.md`](../backend/sql/README.md) y [`backend/sql/schema.txt`](../backend/sql/schema.txt) con las cinco migraciones reales.
- [x] Limpiar enlaces rotos en [`docs/README.md`](README.md).

### PR2 — Identificación del modelo activo (✅ implementado)

Objetivo cumplido: un operador o el sistema puede saber **qué modelo está sirviendo predicciones, con qué métricas y cuándo se entrenó**, sin abrir el panel ni leer logs.

Componentes:

- [x] Migración `006_model_versions.sql` con tabla `model_versions` (`id`, `model_version`, `base_version`, `loaded_at`, `file_mtime`, `file_size_bytes`, `is_synthetic`, `trained_on_games`, `val_accuracy_home`, `val_mae_total_runs`, `val_proba_home_std`, `split_mode`, `val_from_requested`, `feature_names_json`, `loaded_by`, `notes`, `is_active`). Índice parcial UNIQUE garantiza una sola fila activa.
- [x] Modelo SQLAlchemy `ModelVersion` en `models/mlb.py`.
- [x] `services/model_registry.py`: `record_model_load`, `get_active_model_version`, `list_model_versions`, `backup_model_file`, `quick_inspect_bundle`.
- [x] Insertar una fila al cargar el modelo (`lifespan` y `POST /admin/model/reload`) con la metadata leída de `training_meta` del bundle. La idempotencia por `model_version` permite recargar sin proliferar filas.
- [x] **Endpoint público** `GET /api/v1/model/info` (`PublicModelInfoResponse`): `model_loaded`, `model_version`, `base_version`, `is_synthetic`, `loaded_at`. Sin métricas detalladas por defecto.
- [x] **Endpoint admin** `GET /admin/model/versions?limit&offset` (`AdminModelVersionsResponse`) con histórico paginado y métricas completas para rollback consciente.
- [x] **Footer global** en la app pública (`ModelFooterComponent` + `ModelInfoService`) con polling cada 5 min, etiqueta corta y tooltip con detalle. Estilo verde (real) / amarillo (sintético) / rojo (no cargado).
- [x] **Banner amarillo** en `/operations` cuando `model_version` empieza por `rf-synthetic`.
- [x] **Backup automático** del joblib previo al lanzar `POST /admin/pipeline/train` (nombre `model.joblib.bak.<UTC ISO>`).
- [x] Tests `test_model_registry.py` (7 cubren registro, idempotencia, flag sintético, unicidad de activo, listado y backup).

### PR3 — Tests admin / auth / scheduler (✅ núcleo implementado)

Objetivo: red de seguridad sobre el código admin, que hoy es el camino crítico de operación pero no tiene tests.

Componentes:

- [x] `tests/test_admin_security.py`: hash + verify, create/decode token, decode_expires_at, password demasiado larga.
- [x] `tests/test_admin_auth_service.py`: `login_with_password` (OK, password mal, inactivo, JWT vacío).
- [x] `tests/test_routes_admin_auth.py` (httpx + ASGI, SQLite + override `get_db`): `/auth/ready`, `/auth/login` (401, rate-limit 429), bootstrap (404 / 200 / 403), `/auth/me`, `/auth/refresh`, CSRF cookie sin `X-Requested-With`, endpoint protegido sin auth (401).
- [x] `tests/test_mlb_daily_snapshot.py`: `_seconds_until_next_utc_run` (mismo día / día siguiente), `run_mlb_daily_snapshot` con `async_session_factory` en SQLite y mocks, `run_mlb_daily_snapshot_job` delega.
- [x] `tests/conftest.py`: motor SQLite en memoria, override de `get_db`, autouse que limpia `_login_attempts` entre tests.

Pendiente opcional (ampliar cobertura):

- [ ] `tests/test_routes_admin_pipeline.py`: rebuild snapshots con mock de MLB, `clear cache`, evaluate pending, `train` con subprocess mockeado.
- [ ] `POST /auth/logout` explícito en test (hoy no hay aserción dedicada).

---

## Mejoras inmediatas no bloqueantes (post-MVP-1)

- [ ] **Cobertura de snapshots para `week`**: parametrizar `UPCOMING_SNAPSHOT_DAYS` (env var + flag en panel), default 7-9. Recalcular features para días futuros también.
- [ ] **Limpiar scripts ad-hoc** del root del backend (`profile_*.py`, `test_tarpit*.py`): mover a `scripts/` o eliminar.
- [ ] **Auditar `backend/.env`** versionado: revisar `.gitignore` y rotar credenciales si hubo secretos reales.
- [ ] **Persistir progreso del backfill** en BD (no solo `app.state`) para sobrevivir a reinicios.
- [ ] **Footer público** mostrando versión del modelo y enlace a documentación interactiva (`/docs`).

---

## MVP-2 — backlog de diseño

Cuando cerremos PR1+PR2+PR3, abrir un nuevo documento `docs/vision-mvp2.md` con:

1. **Multi-sport real**:
   - Migración para añadir `sport_code` a `games` (default `"mlb"`).
   - Extender `backend/src/app/sports/` con un adapter por deporte (hoy es solo un Protocol vacío).
   - Pipelines de ingesta para fútbol (API-Sports) y NBA (statsapi.nba.com o equivalente).
   - Frontend: convertir `coming-soon` en vistas funcionales.
2. **Re-entrenamiento programado**:
   - Cron real (Render Cron Service o GitHub Action) que entrene cada N días si hay nuevos datos.
   - Drift detection: alerta si la accuracy del último mes cae > X% respecto al baseline.
   - Promoción automática vs aprobación humana (decisión de producto).
3. **Auth pública** (opcional):
   - Tabla `users` separada de `admin_users`.
   - Favoritos por equipo, alertas por email cuando juegue mi equipo.
4. **Observabilidad**:
   - Sentry para excepciones (frontend + backend).
   - Métricas Prometheus expuestas en `/metrics` (latencia, errores 5xx, hits/miss de caché de predicciones, freshness del último sync).
   - Structured logs con `request_id`.
5. **Retención de datos**:
   - Particionamiento de `games` por temporada (PostgreSQL declarative partitioning).
   - CLI `db-purge --season 2024` que borre `boxscore_json` y `lineups_json` viejos pero conserve `games`, `prediction_results` y `game_feature_snapshots`.
   - Tabla `historical_stats` con agregados de jugador/equipo para no perder contexto.
6. **CI/CD** (también puede entrar antes):
   - GitHub Actions: `pytest`, `ruff`, `mypy`, `ng test`, `ng build`.
   - Vercel preview por PR.
   - Render preview por PR (si el plan lo permite).
7. **Tests E2E** del flujo crítico (Playwright o Cypress).
8. **i18n** si decidimos abrir mercado fuera de español.
9. **Explicabilidad** (SHAP) por partido, opcional.

---

## Notas

- El orden PR1 → PR2 → PR3 maximiza valor por esfuerzo: docs primero porque son baratas y desbloquean a cualquier desarrollador que abra el repo; luego el modelo (visible para todos), y por último la red de seguridad de tests.
- Los pendientes de producto (decisiones abiertas) están en [pendientes.md](pendientes.md), no aquí. Aquí solo van **acciones técnicas concretas**.

### Flujo Git y pull requests (cuándo abrir PR y merge)

No hace falta esperar al final del trabajo para revisar en GitHub. Lo habitual es:

1. **Rama por bloque** (recomendado para diffs pequeños): `docs/…`, `feat/…`, `test/…`, cada una con su PR contra `main`, merges en orden.
2. **Una rama con varios commits atómicos**: un solo PR; los revisores pueden ir commit por commit (en GitHub: *Commits* del PR).

Tras `git push -u origin <rama>`, abre el PR en la UI de GitHub (*Compare & pull request*) o instala la CLI [`gh`](https://cli.github.com/) y usa `gh pr create`. En este entorno no suele estar `gh`; el push y el PR los haces en tu máquina o en CI.

Rama actual de referencia (modelo + tests): `feat/model-registry-and-admin-tests` (commits separados: PR2 / PR3).
