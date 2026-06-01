# Runbook: (re)entrenar el modelo

Guía reproducible para entrenar por primera vez o re-entrenar el modelo de predicción
de MLB.

> **El algoritmo es Random Forest**, no KNN: `RandomForestClassifier` (probabilidad de
> victoria local) + `RandomForestRegressor` (carreras totales) — ver
> `src/app/ml/train_from_db.py` y `src/app/ml/predictor.py`.

Todos los comandos se ejecutan desde `Sports-Predictions/backend/`. Python ≥ 3.12.

---

## 0. Instalación (una sola vez)

```bash
cd Sports-Predictions/backend
pip install -e ".[dev]"        # o: uv pip install -e ".[dev]"
cp .env.example .env           # editar valores
```

Variables mínimas en `.env`:

| Variable | Valor |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://USER:PASS@HOST:5432/DB` — en Supabase free tier usar el *transaction pooler* si el directo es IPv6-only |
| `ADMIN_JWT_SECRET` | cadena fuerte ≥ 16 chars (necesaria para el panel y el endpoint de train) |
| `ML_MODEL_PATH` | vacío → usa `src/app/ml/artifacts/model.joblib` |

---

## 1. Crear el esquema de BD (solo BD nueva)

Aplicar en orden los `.sql` de `backend/sql/` sobre la BD destino (usar la URL **sin**
`+asyncpg` para `psql`):

```bash
for f in sql/001_*.sql sql/002_*.sql sql/003_*.sql sql/004_*.sql \
         sql/005_*.sql sql/006_*.sql sql/007_*.sql; do
  psql "postgresql://USER:PASS@HOST:5432/DB" -f "$f"
done
```

Si la BD del MVP ya existe, saltar este paso (aplicar solo migraciones nuevas).

---

## 2. Crear usuario admin (para el panel de Operaciones)

```bash
create-admin --username admin --password 'TU_PASSWORD_FUERTE'
# alternativa:
PYTHONPATH=src python -m app.cli.create_admin --username admin --password '...'
```

---

## 3. Backfill de histórico MLB

Puebla las tablas `games` y `game_weather` desde statsapi.

```bash
python -m app.cli.backfill_history --start 2025-03-20 --end 2025-09-30 --sleep 0.3
```

- `--fetch-details` (default `true`) trae boxscore/alineaciones — necesario para ERA.
- Tope por petición HTTP del API MLB: 7 días; el CLI itera por día con `--sleep` para no
  saturar statsapi. Una temporada completa tarda; vigilar egress de Supabase.

---

## 4. Recalcular feature snapshots

Genera `game_feature_snapshots` (las 13 features de entrenamiento).

```bash
python -m app.cli.rebuild_feature_snapshots --season 2025 --window 10
```

- `--window`: ventana móvil de victorias/carreras (default 10).
- Sin `--season` reconstruye todo (más lento).
- Features producidas: `home/away_wins_roll`, `home/away_runs_avg_roll`,
  clima (temperatura/humedad/viento/elevación), `home/away_starter_era`,
  `home/away_bullpen_era`, `defaults_injected`.

---

## 5. Entrenar el Random Forest

```bash
python -m app.ml.train_from_db \
  --output src/app/ml/artifacts/model.joblib \
  --model-version rf-db-v1 \
  --season 2025 \
  --trees 128 --max-depth 16 --min-samples-leaf 2 \
  --val-from 2025-08-01
```

- Requiere ≥ 20 partidos etiquetados (`home_win`/`total_runs` no nulos) o falla.
- Partición **temporal** (sin shuffle): fechas `< --val-from` → train;
  `>= --val-from` → validación. Sin `--val-from` usa 80/20 por fecha.
- Logea `val_accuracy_home`, `val_mae_total_runs`, `val_proba_home_std`. Si
  `val_proba_home_std ≈ 0` las features están planas → revisar pasos 3–4.
- Genera un bundle joblib: `clf`, `reg`, `feature_names`, `model_version`, `training_meta`.

Hiperparámetros (flags): `--trees` (n_estimators), `--max-depth` (mayor → más variación
en `predict_proba`, más riesgo de sobreajuste), `--min-samples-leaf` (menor → árboles
más finos y probabilidades más dispersas).

---

## 6. Activar el modelo entrenado

- **Por reinicio:** dejar el archivo como `src/app/ml/artifacts/model.joblib` (o apuntar
  `ML_MODEL_PATH`) y reiniciar la API; el `lifespan` lo carga y lo registra en
  `model_versions`.
- **En caliente (sin reinicio):** `POST /api/v1/admin/model/reload` (autenticado).
  La versión pasa a `rf-db-v1@<mtime_hex>`, lo que **invalida automáticamente** la caché
  de predicciones (`game_prediction_cache` compara `model_version`).

### Alternativa: todo desde el panel de Operaciones

Con sesión admin, en orden:
`POST /admin/pipeline/backfill` (background) →
`POST /admin/pipeline/rebuild-snapshots` →
`POST /admin/pipeline/train` (subproceso, timeout 900 s, hace backup del `.joblib`
previo) →
`POST /admin/model/reload`.

---

## 7. Verificación

```bash
curl -s localhost:8000/api/v1/admin/model/versions    # autenticado: historial
curl -s localhost:8000/api/v1/model/info               # versión activa
curl -s "localhost:8000/api/v1/games?date=2025-08-15&include_predictions=true"
```

Criterios de éxito:

- `model_versions` muestra la fila nueva con `is_active=true` y métricas pobladas.
- `val_accuracy_home` razonable (> ~0.5) y `val_proba_home_std` > 0 (no todo plano).
- Las predicciones devuelven probabilidades **dispersas** entre partidos, no un valor
  constante (~0.48 indica features planas / modelo degenerado).
- El dashboard de Backtest refleja el rango entrenado/validado.
