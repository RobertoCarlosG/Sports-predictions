# Evolución técnica: sync, box score y alineaciones

Documento de **historial técnico** y de las **decisiones que ya están en código**. Para el resumen de producto actual, ver [vision-y-alcance.md](vision-y-alcance.md) y [estatus-actual.md](estatus-actual.md). Para los pendientes vivos, ver [pendientes.md](pendientes.md) y [proximos-pasos.md](proximos-pasos.md).

---

## 1. Box score en la UI

**Estado actual (implementado)**

- Componente `app-boxscore-view`: tabla **R / H / E**, abreviaturas y **carreras por inning** si el JSON incluye `teams.*.innings`.
- Acordeón **«JSON completo»** para depuración o payloads grandes.
- El backend persiste el payload completo en `boxscore_json` vía `MlbApiClient.boxscore` cuando `fetch_details=true`.
- Util de parseo en `frontend/src/app/utils/boxscore-parse.ts`.

**Mejora futura no bloqueante**

- Resaltar línea de pitcheo o bateadores clave; vista más rica en móvil. Pendiente de necesidad de producto.

**Archivos**

- `frontend/src/app/boxscore-view/`, `frontend/src/app/utils/boxscore-parse.ts`, `frontend/src/app/game-detail/game-detail.component.html`
- `backend/src/app/services/mlb_client.py`, `backend/src/app/services/mlb_sync.py`, `backend/src/app/models/mlb.py` (`boxscore_json`)

---

## 2. «Sincronizar rango» y timeouts (Render / Vercel)

**Síntoma original (resuelto)**

- `OPTIONS` al `POST` con 200, pero el **POST** no completaba o el servicio reiniciaba: una sola petición recorría muchos días y muchas llamadas HTTP a MLB, superando el **timeout del proxy** (Render).

**Causa**

- No es CORS en sí: el *preflight* es normal. El cuello de botella era **duración de la petición** y volumen de trabajo en un solo hilo de request.

**Implementado**

| Enfoque | Descripción | Estado |
|---------|-------------|--------|
| Chunks en el cliente | El historial MLB encadena **un día** por `POST /mlb/sync-range`. | ✅ |
| Límite en servidor | **Máximo 7 días** de calendario por **una** llamada a `sync-range` (validación `MlbSyncRangeBody` + tope absoluto 370). | ✅ |
| Sync por partido | `POST /mlb/games/{game_pk}/sync` + botón **«Actualizar desde MLB»** en el detalle. | ✅ |
| **Backfill admin en segundo plano** | `POST /admin/pipeline/backfill` con `BackgroundTasks`, persiste estado en `app.state.backfill_job` (memoria) consultable vía `GET /admin/pipeline/backfill-status`. UI con barra de progreso + polling cada 2 s + renovación automática de JWT. | ✅ |
| **ETL diario en proceso** | `daily_snapshot_loop_forever` (lifespan), opt-in con `MLB_DAILY_SNAPSHOT_ENABLED=true`. Importa hoy+mañana UTC + recalcula snapshots. | ✅ |

**Pendientes opcionales (no bloquean MVP-1)**

- **Cron real fuera del proceso** (Render Cron Service o GitHub Action programada): hoy si el API se reinicia o duerme, el job no corre. Ver [pendientes.md](pendientes.md) §⚙️ y [proximos-pasos.md](proximos-pasos.md).
- **Persistir `backfill_job`** en BD (no solo memoria) para no perder el progreso si el proceso reinicia. Hoy el backfill **sí se mantiene** en BD (los `games` ya creados quedan), pero el panel olvida el estado del job.

**Archivos**

- `backend/src/app/api/routes/mlb.py` — `sync_mlb_date_range`, `sync_mlb_single_game`
- `backend/src/app/api/routes/admin.py` — `admin_backfill`, `admin_backfill_status`, `admin_mlb_daily_snapshot`
- `backend/src/app/services/mlb_sync.py` — `sync_games_for_date`, `sync_single_game`
- `backend/src/app/services/admin_backfill_state.py` — tracking en memoria
- `backend/src/app/services/mlb_daily_snapshot.py` — `daily_snapshot_loop_forever`, `run_mlb_daily_snapshot`
- `frontend/src/app/mlb-history/mlb-history.component.ts`, `frontend/src/app/services/games-api.service.ts`
- `frontend/src/app/operations/operations.component.ts`

---

## 3. Sync partido a partido

- **Backend**: `POST /api/v1/mlb/games/{game_pk}/sync` con cuerpo `{ "fetch_details": true|false }`; usa `schedule?gamePk=` y `sync_single_game` en `mlb_sync.py`.
- **Frontend**: `GamesApiService.syncMlbGame` y botón en detalle.
- Tras el sync se invalidan cachés cliente del partido y de la lista, y se dispara `refresh_prediction_cache_for_games` en `BackgroundTasks` si `PIPELINE_AUTO_CACHE_PREDICTIONS=true`.

---

## 4. Alineaciones / feed

**Problema (resuelto)**

- Las alineaciones se intentaban guardar solo desde `/game/{pk}/feed/live`. Ese endpoint suele devolver **404** en partidos **ya finalizados**; el **box score** sí incluye `batters` / `players` / `battingOrder`.

**Solución en código**

- Tras el *live* feed, si no hay payload útil, se rellenan alineaciones con **`lineups_from_boxscore()`** (estructura con `source: "boxscore"` y listas de bateadores por equipo).
- Para repoblar partidos antiguos en BD: vuelve a sincronizar con **«Incluir boxscore / live»** o usa **«Actualizar desde MLB»** en el detalle.

---

## 5. Variables de entorno y base de datos

- **Producción**: pooler transaccional de Supabase; ver [errores_direct_connection.md](errores_direct_connection.md).
- **Motor**: `NullPool` y desactivar caches de prepared statements problemáticos con PgBouncer; ver `backend/src/app/db/session.py`.
- **`SET LOCAL statement_timeout`**: `mlb_sync.py` aplica un timeout mínimo de 300 s por transacción al escribir boxscore (`_set_local_statement_timeout_for_mlb_write`) para evitar `QueryCanceled` con JSON grande o contención de locks.
- **Variables clave**: ver [`backend/.env.example`](../backend/.env.example) y la configuración tipada en `backend/src/app/core/config.py`.

---

## 6. Línea de evolución (estado actual)

**Hecho:**

1. Sync por `game_pk`, chunks de rango, UI de box score, alineaciones desde box score.
2. Backfill admin en segundo plano con tracking, UI con barra de progreso.
3. ETL diario opt-in en proceso del API.
4. Evaluación automática de predicciones tras sync de partidos finales.

**Próximo (PR siguientes y MVP-2):**

- Cron real fuera del proceso (no bloquea MVP-1, sí mejora robustez).
- Tabla `model_versions` para historial de modelos (PR2).
- Tests del scheduler `mlb_daily_snapshot` y de admin/auth (PR3).
- Persistir progreso del backfill en BD (calidad de vida del operador).
- Particionamiento por temporada y *spring cleaning* de JSON pesados (MVP-2). Diseñado en [diseno-pipeline-predicciones.md §8](diseno-pipeline-predicciones.md).
