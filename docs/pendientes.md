# Pendientes y decisiones abiertas

Este archivo recoge **decisiones de negocio, datos y producto** que aún no se han cerrado.

- El **estado técnico** del producto (qué está hecho) está en [vision-y-alcance.md](vision-y-alcance.md), [estatus-actual.md](estatus-actual.md) y [estado-real-mvp1.md](estado-real-mvp1.md).
- El **roadmap inmediato** y los hitos técnicos del MVP-1 → MVP-2 están en [proximos-pasos.md](proximos-pasos.md).

---

## ✅ Resueltos en MVP-1 (referencia, antes estaban como pendientes)

- **Lista inicial de estadios MLB** + carga de coordenadas: [`backend/src/app/data/mlb_stadiums.json`](../backend/src/app/data/mlb_stadiums.json).
- **Predicción Random Forest** entrenable contra la BD: `backend/src/app/ml/train_from_db.py` + `feature_snapshots.py`. El modelo sintético (`training.py`) queda solo como fallback de desarrollo (`ML_AUTO_SYNTHETIC_ON_MISSING`).
- **Over/under** expuesto como `over_under_line` en API y dashboard.
- **Sync estable** para rangos: chunks en cliente, límite ≤ 7 días por petición, sync por partido, box score y alineaciones desde boxscore cuando el live feed falla. Detalle en [pendientes-sync-boxscore.md](pendientes-sync-boxscore.md).
- **Panel `/operations`** con login JWT (cookie HttpOnly, rate-limit, refresh, bootstrap del primer usuario).
- **Evaluación automática de aciertos** (`predicted_winner`, `actual_winner`, `is_correct`, `evaluated_at`) tras cada sync de partidos finales.
- **Métricas y backtest** (`/admin/predictions/metrics`, `/predictions/evaluations`, `/predictions/backtest`) con dashboard en `/operations`.
- **ETL diario opt-in** (`MLB_DAILY_SNAPSHOT_ENABLED=true`) y bajo demanda desde el panel.
- **Backfill por fechas** en segundo plano con tracking (`/admin/pipeline/backfill` + `/backfill-status`).

---

## 🟡 Pendientes inmediatos (necesarios para cerrar MVP-1)

Estos están en **PRs abiertos** o muy cerca; ver [proximos-pasos.md](proximos-pasos.md).

- [x] **Identificar el modelo activo** desde la app pública: ✅ PR2 implementado. Tabla `model_versions`, `GET /api/v1/model/info` (público), `GET /admin/model/versions` (histórico admin), footer con `ModelInfoService`, banner amarillo en `/operations` cuando es sintético, backup automático del joblib antes de entrenar.
- [ ] **Cobertura de snapshots para `week`**: subir `UPCOMING_SNAPSHOT_DAYS` (parametrizable) o exponer botón explícito; hoy es 1 → la vista «Semana» tiene P(home) ≈ 0.5 a partir del día +2.
- [ ] **Tests de admin/auth/scheduler** (PR3): hoy `tests/` no cubre `routes/admin.py`, `core/admin_security.py`, ni `mlb_daily_snapshot.py`.
- [ ] **Documentar migraciones SQL** y mantener `schema.txt` al día. Cubierto en este PR de docs (ver [migraciones.md](migraciones.md)).
- [ ] **Limpiar scripts ad-hoc** del root del backend (`profile_*.py`, `test_tarpit*.py`).
- [ ] **Banner de "modelo sintético"** en frontend cuando `model_version` empiece por `rf-synthetic`.

---

## 🟠 Pendientes de negocio / datos

- [ ] **Validar coordenadas** de todos los `venue_id` MLB frecuentes (algunos parques tienen estadios secundarios o cambios de temporada).
- [ ] **Definir accuracy mínima aceptable** del modelo en producción (umbral para `val_accuracy_home` y `val_proba_home_std`). Hoy se loguea pero no se bloquea la promoción del modelo.
- [ ] **Retención de datos**: cuántas temporadas mantener "calientes". Cuándo mover `boxscore_json` y `lineups_json` a *cold storage* (S3, dump) y truncar. Particionamiento por temporada cuando crezca el volumen — diseñado en [diseno-pipeline-predicciones.md §8](diseno-pipeline-predicciones.md), no implementado.
- [ ] **Criterios de re-entrenamiento**: frecuencia, drift detection, dataset (ventana móvil vs temporada completa).
- [ ] **Política de versionado del modelo**: quién promueve, criterios de rollback (apoya en PR2 con tabla `model_versions`).

---

## 🔵 Decisiones abiertas (de producto)

- **¿Auth pública en el dashboard?** MVP-1 es lectura abierta. MVP-2: ¿favoritos por usuario? ¿alertas? ¿tier de pago?
- **¿Explicabilidad avanzada (SHAP, importancia por feature)?** Útil para transparencia pero suma complejidad de UI y cómputo.
- **¿Prioridad MVP-2: profundizar MLB o abrir fútbol/NBA?** El layer de adapters (`backend/src/app/sports/history_template.py`) está esbozado pero `games.sport_code` aún no existe.
- **¿i18n?** Hoy todo en español hardcoded.

---

## ⚙️ Pendientes operativos / infraestructura (sin bloquear MVP-1)

- [ ] **CI/CD** (GitHub Actions): `pytest` + `ruff` + `mypy` en backend; `ng test` + `ng lint` en frontend; build de Docker/Vercel preview en PRs.
- [ ] **Cron real** fuera del proceso (Render Cron Service o GitHub Action programada) para que el ETL no dependa de un proceso vivo.
- [ ] **Observabilidad**: structured logging con `request_id`, Sentry para excepciones, métricas Prometheus (latencia, errores 5xx, hits/miss de caché).
- [ ] **Tests E2E** del flujo crítico (Playwright / Cypress).
- [ ] **Rotación / auditoría de secretos** versionados accidentalmente (revisar `.gitignore` de `backend/.env`).
- [ ] **Backup del `model.joblib`** previo al sustituirlo (sin esto, un mal entrenamiento sobrescribe el modelo bueno).

---

**Documentación transversal:** [deploy.md](deploy.md) · [README.md](README.md) (índice) · reglas globales en `../../docs/estilo-programacion.md`.
