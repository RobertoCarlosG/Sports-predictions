# Estado real del MVP-1 — Sports-Predictions

**Última revisión:** 7 de mayo de 2026 (post-PR1 de docs).
**Autor:** auditoría de código del repo (`backend/`, `frontend/`, `docs/`).
**Propósito:** documento honesto de **dónde estamos hoy**, contrastando lo que dicen los docs con lo que está realmente implementado en el código. Pensado como punto de partida para cerrar el MVP-1 y abrir el diseño del MVP-2.

> **Nota tras PR1 (docs):** los gaps de tipo "documentación desactualizada" (D1-D8 en la versión anterior de este doc) ya están **cerrados**: `vision-y-alcance.md`, `estatus-actual.md`, `pendientes.md`, `pendientes-sync-boxscore.md`, `Comportamiento-predicciones.md` y `diseno-pipeline-predicciones.md` ahora reflejan el código real. Se creó [`migraciones.md`](migraciones.md) y [`proximos-pasos.md`](proximos-pasos.md). Los gaps que quedan son **de código y datos**, listados a continuación.

> Si una sección dice **«implementado»** es porque existe en `main`. Si dice **«parcial»** o **«gap»**, hay distancia entre el comportamiento esperado y lo que hay en código.

---

## 1. Resumen ejecutivo (TL;DR)

- El MVP-1 está **funcionalmente completo** en su núcleo: ingesta MLB → BD → features → modelo → API → dashboard, con panel **Operaciones** autenticado, evaluación de aciertos/fallos, backtesting y un job ETL diario opcional.
- **PR1 cerró el bloque de documentación**: los docs ya reflejan el código real (admin, evaluación, backtest, daily job, `train_from_db`, todas las migraciones SQL). Los enlaces rotos están corregidos.
- **PR2 (en cola)** abordará la identificación del modelo activo. El modelo en producción **es el real** (`rf-db-v*`, no sintético), pero hoy no hay forma fácil de auditarlo desde fuera del panel: hace falta tabla `model_versions`, endpoint público `GET /api/v1/model/info` y banner UI.
- **PR3 (en cola)** cubrirá con tests `routes/admin`, auth/JWT y scheduler diario, que hoy son el camino crítico de operación sin red de seguridad.
- **Lo que sigue siendo gap real** (ver §4 abajo) tras PR1:
  1. **Identificación del modelo activo** desde la app pública (M1) — bloque del PR2.
  2. **Cobertura de predicciones para "Esta semana"**: `UPCOMING_SNAPSHOT_DAYS = 1`, los partidos a 3-7 días caen al fallback de constantes (M2).
  3. **Tests** de admin/auth/scheduler (T1, T2) — bloque del PR3.
  4. Limpieza de scripts ad-hoc, auditoría de `.env`, backup del modelo previo, persistencia del backfill (varios menores).
- El cierre del MVP-1 razonable es **PR2 + PR3** (≈ 3-5 días de trabajo).

---

## 2. Mapa real del código vs documentación

### 2.1 Backend (`backend/src/app/`)

| Área | Lo que el doc dice (`estatus-actual.md` / `vision-y-alcance.md`) | Lo que hay realmente | Estado |
|------|------------------------------------------------------------------|---------------------|--------|
| Routers | `health`, `games`, `mlb`, `predict` | `health`, `games`, `mlb`, `predict`, **`admin` (no documentado)** | **gap doc** |
| Predicción | `GET /predict/{game_pk}` | `GET /predict/{pk}` + **`POST /predict/{pk}/refresh`** + `prediction_results` con caché por `model_version` | **gap doc** |
| Sync MLB | `sync-range` (≤ 7 días), `single-game` | Ambos + **`backfill` con tracking en BD** + **daily snapshot job en lifespan** | **gap doc** |
| Predicciones evaluadas | No mencionado | `prediction_results.predicted_winner / actual_winner / is_correct / evaluated_at` + `evaluate_predictions_for_final_games` automático tras sync | **gap doc** |
| Métricas / Backtest | No mencionado | `GET /admin/predictions/metrics`, `/predictions/evaluations`, `/predictions/backtest` con summary, timeseries y filas ML+O/U | **gap doc** |
| Auth admin | "MVP sin login" | JWT HS256 en cookie HttpOnly, bootstrap, login, refresh, rate-limit por IP, CLI `create-admin` | **gap doc** |
| Pipeline batch | "Posible mejora futura: worker de fondo" | `daily_snapshot_loop_forever` corre en `lifespan` cuando `MLB_DAILY_SNAPSHOT_ENABLED=true` (sync hoy+mañana UTC + rebuild snapshots). Backfill admin con `BackgroundTasks`. | **gap doc** |
| Modelo | "Random Forest sintético" | `train_default_model` (sintético, fallback) + **`train_from_db.py`** (real, lee `game_feature_snapshots` + etiquetas, partición temporal, métricas de validación, manifiesto en `training_meta`) | **gap doc** |
| Features | "placeholders 0.5 / 4.5" | 13 features reales (`FEATURE_NAMES`): rachas, runs rolling, clima (4), ERA abridor home/away, ERA bullpen home/away, **flag `defaults_injected`**. Caché `pitching_era_cache`. | **gap doc** |
| Cobertura snapshots | No detalla | Recalcula **toda la BD** ordenada cronológicamente para rolling windows; persiste solo temporada filtrada + **+1 día futuro** (`UPCOMING_SNAPSHOT_DAYS`). | **parcial** (solo +1 día) |
| Tests | Generales | `tests/`: backtest, config, db_url, feature_snapshots, health, mlb_client, mlb_sync, prediction_cache, predictor. **No hay** tests de admin/auth, daily-snapshot, train_from_db, pipeline_hooks. | **parcial** |

### 2.2 Frontend (`frontend/src/app/`)

| Área | Doc | Realidad | Estado |
|------|-----|----------|--------|
| Rutas | "listado por fecha + historial + detalle" | `mlb/today`, `mlb/tomorrow`, `mlb/week`, `mlb/history`, `mlb/game/:pk`, `operations`, `soccer`, `nba` (las dos últimas → `coming-soon`) | **gap doc** |
| Predicciones en UI | No detalla evaluación | `match-card` con badges Hit/Miss verde/rojo y % de confianza (alineado con `Comportamiento-predicciones.md`) | OK |
| Caching cliente | No documenta | `RequestCache` con `shareReplay(1)` + TTL por entidad + `signal/computed` en `game-list` | **gap doc** |
| Operaciones | No documenta | Componente `operations`: tabs Backtest + ETL, login JWT, formularios de backfill/rebuild/train/reload, polling de progreso, renovación automática del token | **gap doc** |
| Backtest | No documenta | `backtest-dashboard` con summary ML+O/U, serie temporal y tabla de partidos con filtro de confianza mínima | **gap doc** |
| Otros deportes | "Estructura permite añadir" | UI en `coming-soon`; **no hay** integración real, tabla `games` no tiene `sport_code` | **gap doc + gap código** |

### 2.3 Base de datos (`backend/sql/`)

Migraciones aplicadas (manualmente; sin Alembic):

| Script | Contenido | Doc lo menciona |
|--------|-----------|-----------------|
| `001_initial_schema.sql` | Esquema base | Sí |
| `002_game_scores.sql` | Marcadores | Sí |
| `002_prediction_cache_and_admin.sql` | `prediction_results`, `admin_users` | **No (en `estatus-actual.md`)** |
| `003_pitching_and_starters.sql` | `pitching_era_cache`, `home/away_starter_id` | **No** |
| `004_prediction_evaluation.sql` | `predicted_winner`, `actual_winner`, `is_correct`, `evaluated_at` | **No** |
| `005_teams_optimization.sql` | Índices anti-lock | **No** |

Riesgo: alguien que despliegue siguiendo solo `vision-y-alcance.md` aplica el `001` y/o `002_game_scores` y arranca el backend → el login del panel devuelve 503 (`admin_users` no existe), las predicciones no se evalúan, y nadie sabe por qué. Esto **ya pasó** y dejó rastro en `admin_auth_ready` del propio código (mensajes de "Falta la tabla admin_users…").

---

## 3. Qué funciona end-to-end (verificado en código)

1. **Ingesta MLB** (`mlb_sync.py`): schedule + boxscore + linescore + live feed; alineaciones derivadas del boxscore si el live feed falla; throttling global con `mlb_throttle.py`; `SET LOCAL statement_timeout` defensivo en escrituras pesadas.
2. **Clima**: Open-Meteo + `mlb_stadiums.json`, persistido en `game_weather`.
3. **Snapshots de features**: `rebuild_game_feature_snapshots` produce filas con rachas N=10, ERA real desde la API (con caché), clima, etiquetas (`home_win`, `total_runs`) cuando el partido es final.
4. **Modelo**: si existe `model.joblib` se carga en `lifespan`; si no, opcionalmente se entrena uno sintético al vuelo (`ml_auto_synthetic_on_missing`).
5. **Predicción**:
   - `GET /predict/{pk}` y `POST /predict/{pk}/refresh` (con caché por `model_version`).
   - `GET /games?include_predictions=true` decide si predecir según ventana temporal (no predice partidos pasados sin caché previa).
6. **Evaluación**: tras `sync_games_for_date`, los partidos finalizados se evalúan automáticamente; `recompute-all-moneyline-evaluations` permite reevaluar tras cambios de lógica.
7. **Operaciones**: backfill por fechas, rebuild snapshots, train, reload, clear cache, evaluate-pending, ETL diario manual, métricas, backtest.
8. **Frontend**: vistas Hoy/Mañana/Semana, historial, detalle (clima, box score, alineaciones, predicción, badges Hit/Miss), Operaciones con tabs Dashboard + ETL.

---

## 4. Dónde estamos fallando (gaps reales)

Clasifico cada gap por **causa** (`omisión`, `falta de tiempo`, `documentación desactualizada`, `decisión abierta`) y **bloquea-MVP1?** (sí/no).

### 4.1 Documentación — ✅ cerrado en PR1

Todos estos gaps (D1-D8) fueron resueltos en el PR de documentación:

| # | Gap | Estado tras PR1 |
|---|-----|-----------------|
| D1 | `estatus-actual.md` desactualizado | ✅ reescrito con admin, evaluación, backtest, daily snapshot, `train_from_db`, todas las rutas. |
| D2 | `pendientes.md` con cosas ya cerradas | ✅ reescrito separando ✅ resuelto / 🟡 inmediato / 🟠 negocio / 🔵 abierto / ⚙️ infra. |
| D3 | `pendientes-sync-boxscore.md` "worker en background pendiente" | ✅ reescrito: el daily snapshot y el backfill admin con tracking son "✅ implementado". |
| D4 | `vision-y-alcance.md` no detalla el modelo real | ✅ reescrito con bundle `training_meta`, `model_version` con sufijo de signatura, fallback sintético. |
| D5 | Enlaces rotos en `docs/README.md` | ✅ reescrito. `proximos-pasos.md` creado; los archivos inexistentes ya no se enlazan. |
| D6 | `SESSION-SUMMARY-2026-04-23.md` referencia 6 archivos inexistentes | ✅ aclarado en `docs/README.md`: el contenido vive en los archivos principales actualizados. |
| D7 | `Comportamiento-predicciones.md` con DTO inventado | ✅ reescrito con `GameDetail` / `PredictionOut` reales. |
| D8 | `diseno-pipeline-predicciones.md` sin marcar etapas | ✅ etapas A-D marcadas (✅ implementado / 🟡 pendiente). |

**Bonus de PR1:**

- `docs/migraciones.md` nuevo: orden, dependencias, troubleshooting, convenciones, próximas migraciones.
- `backend/sql/README.md` y `backend/sql/schema.txt` actualizados con las cinco migraciones reales.
- `proximos-pasos.md` nuevo: roadmap PR1 → PR2 → PR3 → MVP-2.

### 4.2 ML, datos y predicción

| # | Gap | Causa | Bloquea MVP-1 |
|---|-----|-------|----------------|
| M1 | **No hay garantía de que el `model.joblib` activo sea el real**. Se puede estar sirviendo `rf-synthetic-v0` en producción si nunca se corrió `train_from_db` + reload. **El panel `/admin/status` lo muestra**, pero ningún check automatizado lo audita. | falta de tiempo | **Sí**: un MVP de "predicción deportiva" sirviendo modelo aleatorio es un fallo de producto, no de código. |
| M2 | **Cobertura de snapshots incompleta para `week`**: `UPCOMING_SNAPSHOT_DAYS = 1`. Los partidos de día +2 a día +7 caen al fallback de constantes → P(home) ≈ 0.5, O/U ≈ 4.5 + ruido. La UI lo refleja con avisos en `meta.warnings`, pero el usuario ve probabilidades planas sin saber por qué. | omisión | **Sí** para que `week` tenga sentido como producto. |
| M3 | **No hay re-entrenamiento programado**. El daily snapshot solo recalcula features y limpia caché; **no entrena**. El `model.joblib` queda congelado hasta que un humano corra `train_from_db` desde Operaciones. | falta de tiempo / decisión abierta | No (decisión abierta en `pendientes.md`), pero sí limita el valor: el modelo no aprende del histórico nuevo. |
| M4 | **No hay umbral mínimo de calidad** ni alerta de drift. Un entrenamiento que produce `val_accuracy=0.51` y `val_proba_home_std≈0.01` se promueve al recargar igual que uno bueno; queda solo en el log. | omisión | No (es de monitoreo) |
| M5 | **Modelo solo MLB**. `sport_code` no existe en `games`; `feature_snapshots` y `predictor` asumen MLB. Fútbol/NBA tienen UI `coming-soon` pero ningún backend. | decisión consciente de MVP | No (MVP es MLB), **sí para MVP-2**. |
| M6 | **Features pobres**: 13 dimensiones, ninguna por jugador real (lineup, fatiga, splits L/R), park factor binario implícito en `elevation_m`. `pendientes.md` ya lo lista como "señal de oro" para MVP-2. | falta de tiempo | No para MVP-1 |
| M7 | **No persistimos backups del modelo**. Cada `train_from_db --output …` sobrescribe el archivo si se apunta al mismo path. La caché se versiona por `model_version + mtime_ns`, pero perdemos el `joblib` viejo si rompe el nuevo. | omisión | No, pero arriesgado |

### 4.3 Operaciones / despliegue

| # | Gap | Causa | Bloquea MVP-1 |
|---|-----|-------|----------------|
| O1 | El "ETL diario" corre **dentro del proceso del API** (`asyncio.create_task` en `lifespan`). En Render free tier (sleep automático) o tras un reinicio nocturno, el job **no se ejecuta**. No hay cron externo. | decisión consciente / falta de tiempo | No, pero la "automatización" es frágil. |
| O2 | El backfill admin guarda estado en `app.state` (memoria), no en BD. Si el proceso reinicia durante un backfill, se pierde el `BackfillJobStatusResponse`; el sync sí persiste en BD pero el panel "olvida" el progreso. | omisión | No |
| O3 | `.env` está versionado en `backend/` (revisar `.gitignore`). El `.env.example` está bien, pero conviene auditar que no haya secretos en git. | omisión | **Sí si hay secretos reales** |
| O4 | `profile_mlb.py`, `profile_sync.py`, `test_tarpit.py`, `test_tarpit2.py` en raíz de `backend/` son scripts ad-hoc de debugging, no integrados a `pytest` ni documentados. Ensucian el árbol. | omisión | No |
| O5 | **No hay CI/CD verificable**. No detecté `.github/workflows/`. Tests, lint y mypy hay que correrlos a mano. | falta de tiempo | No, **sí para MVP-2** |
| O6 | **No hay observabilidad**: ni Sentry, ni métricas Prometheus, ni structured logs con request_id. Solo `logging` por módulo. | falta de tiempo | No |

### 4.4 Frontend

| # | Gap | Causa | Bloquea MVP-1 |
|---|-----|-------|----------------|
| F1 | Tests `*.spec.ts` mínimos (solo `app.component.spec.ts`). Lógica de signals, caching, evaluación de predicciones y backtest **sin tests**. | falta de tiempo | No |
| F2 | El componente `operations` mezcla auth + ETL + backtest en un solo archivo (~600 LOC TS + HTML + SCSS). Refactor pendiente para separar `operations-auth`, `operations-etl`, `operations-backtest`. | omisión | No |
| F3 | No hay i18n (todo en español hardcoded). Para MVP nacional/regional es OK; para escalar es deuda. | decisión consciente | No |
| F4 | **No hay estado claro de "el modelo activo es sintético"** en la UI pública (sí en `/operations`). Un usuario final puede confiarse en un modelo de prueba sin saberlo. | omisión | **Sí** para honestidad de producto |
| F5 | Tabla `prediction_results` no se muestra en historial: el partido pasado solo trae el badge si la predicción se calculó **antes** del Final. La doc `Comportamiento-predicciones.md` sí prevé el caso D ("Pasado sin predicción") pero no se distingue visualmente del caso C en algunos flujos. | omisión / verificación | No |

### 4.5 Tests / calidad

| # | Gap | Causa | Bloquea MVP-1 |
|---|-----|-------|----------------|
| T1 | No hay tests de `routes/admin.py` (auth, train, backfill, métricas). | falta de tiempo | **Sí** para promover MVP-1 sin sobresaltos |
| T2 | No hay tests de `daily_snapshot_loop_forever` ni del scheduler. | falta de tiempo | No |
| T3 | No hay tests E2E (Playwright/Cypress). | falta de tiempo | No |

---

## 5. ¿Qué falta para "cerrar" el MVP-1?

Reorganizado en **tres PRs** acordados con producto:

### ✅ PR1 — Documentación + migraciones (este PR)

- [x] Reescribir `vision-y-alcance.md`, `estatus-actual.md`, `pendientes.md`, `pendientes-sync-boxscore.md`, `Comportamiento-predicciones.md`. _Cubre D1-D7._
- [x] Marcar etapas A-D en `diseno-pipeline-predicciones.md`. _Cubre D8._
- [x] Crear `proximos-pasos.md` y arreglar enlaces rotos en `docs/README.md`. _Cubre D5, D6._
- [x] Crear [`migraciones.md`](migraciones.md), actualizar [`backend/sql/README.md`](../backend/sql/README.md) y [`backend/sql/schema.txt`](../backend/sql/schema.txt). _Cubre el "documentar migraciones" pedido._

### ✅ PR2 — Identificación del modelo activo (implementado)

Confirmado que **el modelo en producción es real (`rf-db-v*`)** y ahora es **descubrible** sin abrir el panel. Implementado:

- [x] Migración `006_model_versions.sql` con tabla `model_versions` (versión, base, métricas, fecha de carga, autor, notas) e índice parcial UNIQUE para `is_active`.
- [x] Insertar fila al cargar el modelo (`lifespan` y `POST /admin/model/reload`) leyendo `training_meta` del bundle. Idempotente por `model_version`.
- [x] Endpoint público `GET /api/v1/model/info` con la fila activa (mínimo: versión, base, `is_synthetic`, `loaded_at`).
- [x] Endpoint admin `GET /admin/model/versions` con histórico paginado y métricas completas.
- [x] Footer global en frontend público + banner amarillo en `/operations` cuando el modelo es sintético. _Cubre F4._
- [x] Backup automático `model.joblib.bak.<UTC ISO>` previo al lanzar el entrenamiento. _Cubre M7._
- [x] Tests `test_model_registry.py` (7 casos).

### 🟡 PR3 — Tests admin / auth / scheduler

- [ ] `tests/test_admin_security.py`: hash, verify, create_token, decode_token, decode_expires_at_utc.
- [ ] `tests/test_admin_auth.py`: `login_with_password` (usuario inactivo, password mal, JWT secret vacío, OK).
- [ ] `tests/test_routes_admin_auth.py`: bootstrap, login (rate-limit IP), refresh, logout, me, ready.
- [ ] `tests/test_routes_admin_pipeline.py`: rebuild snapshots, clear cache, evaluate-pending, recompute, status, train (subprocess mock).
- [ ] `tests/test_mlb_daily_snapshot.py`: `_seconds_until_next_utc_run`, `run_mlb_daily_snapshot` con sesiones mock.
- [ ] `conftest.py` con fixture de DB SQLite (`aiosqlite`) y override de `get_db`.

### ⏸ Pendientes documentados pero diferidos (post-MVP-1)

- **CI/CD** (GitHub Actions): documentado en [`pendientes.md`](pendientes.md) §⚙️.
- **Cron real** fuera del proceso del API.
- **Snapshots para `week`** (`UPCOMING_SNAPSHOT_DAYS`): mejora menor, pendiente.
- **Limpiar scripts ad-hoc** del root del backend (`profile_*.py`, `test_tarpit*.py`).
- **Auditar `backend/.env`** versionado.
- **Persistir progreso del backfill** en BD (no solo memoria).
- **Tests E2E** (Playwright/Cypress).

---

## 6. Visión y alcance del MVP-1 (re-confirmados)

Para evitar el síndrome de "el alcance se mueve mientras se construye", congelo aquí lo que **sí** es MVP-1:

### En alcance ✅

- **Solo MLB** (datos oficiales de `statsapi.mlb.com`).
- Vistas Hoy / Mañana / Esta semana / Historial / Detalle.
- Predicción con modelo Random Forest entrenado contra **datos reales** (no sintético).
- Evaluación automática de aciertos contra el resultado real.
- Panel **Operaciones** privado con: backfill, rebuild snapshots, train, reload, ETL diario manual, métricas, backtest dashboard.
- Despliegue Supabase + Render + Vercel; sin login en la app pública.

### Fuera de alcance ❌ (es MVP-2 o más)

- Otros deportes (fútbol, NBA): UI `coming-soon` está, integración no.
- Auth para usuarios públicos (favoritos, perfiles).
- SHAP / explicabilidad por partido.
- Cron real fuera del proceso (cron service de Render, GitHub Actions, etc.).
- Particionamiento por temporada y "spring cleaning" de JSON pesados.
- Re-entrenamiento programado con detección de drift.
- Cola de jobs (Celery, RQ) para sync masivos.
- i18n.
- Observabilidad (Sentry / Prometheus / OpenTelemetry).

---

## 7. Pendientes ordenados por causa

### Por **falta de tiempo dedicado** (no es decisión consciente)

- M1 (auditar y promover modelo real)
- M3 (re-entrenamiento programado)
- M4 (umbrales de calidad y drift)
- M6 (features ricas tipo lineup / pitcher)
- O1 (cron real fuera del proceso)
- O5 (CI/CD)
- O6 (observabilidad)
- T1, T2, T3 (tests admin / scheduler / E2E)
- F1 (tests frontend)

### Por **omisión durante el desarrollo**

- D1-D8 (todos los gaps de documentación)
- M2 (snapshots solo +1 día → roto para `week`)
- M7 (no hay backup del modelo previo)
- O2 (estado de backfill solo en memoria)
- O3 (revisar secretos en `.env`)
- O4 (scripts ad-hoc en raíz)
- F2 (refactor de `operations.component`)
- F4 (banner de modelo sintético)
- F5 (caso D del histórico sin predicción)

### **Decisiones abiertas** (no son fallos, solo no se han tomado)

- ¿Auth pública en MVP-2? (`pendientes.md`)
- ¿Retención exacta y particionamiento? (`pendientes.md`, `diseno-pipeline-predicciones.md` §8)
- ¿Prioridad: profundizar MLB o abrir fútbol/NBA en MVP-2?
- ¿Explicabilidad SHAP en MVP-2?
- ¿Coordenadas verificadas para todos los `venue_id` MLB? (`pendientes.md`)

---

## 8. Hand-off al MVP-2 (semilla del próximo doc)

Cuando cerremos el sprint A+B descrito arriba, tiene sentido abrir un nuevo documento **`docs/vision-mvp2.md`** con:

1. Decisión sobre **multi-sport real** vs **profundizar MLB**.
2. Diseño del **Sport Engine / Adapter** (`sport_code` en `games`, registry de features por deporte) — la `sports/history_template.py` ya tiene un Protocol esperando implementación.
3. Pipeline de **re-entrenamiento programado** + criterios de promoción de modelo.
4. **Observabilidad** (qué medir, dónde alertar).
5. **Auth pública** opcional (favoritos por usuario, alertas).
6. Plan de **retención de datos** (particionamiento por temporada, cold storage para `boxscore_json` viejos).

Este documento queda como insumo principal del MVP-2 y como **medida del avance real**: cuando 4.1-4.5 estén marcados, el MVP-1 está cerrado.

---

## 9. Apéndice — comandos de verificación rápida

```bash
# Desde backend/, con DATABASE_URL apuntando a la BD de producción:
python -m app.cli.rebuild_feature_snapshots --season 2026 --window 10
python -m app.ml.train_from_db --output src/app/ml/artifacts/model.joblib --val-from 2026-04-01 --model-version rf-db-v2
# Tras desplegar / copiar el artefacto:
curl -X POST .../api/v1/admin/model/reload -H "Cookie: sp_admin_access=…"
curl .../api/v1/admin/status -H "Cookie: sp_admin_access=…"
curl .../api/v1/admin/predictions/metrics -H "Cookie: sp_admin_access=…"
```

Si `admin/status` reporta `Versión activa: rf-synthetic-v0@…`, **el MVP-1 todavía no está listo** aunque el código lo esté.
