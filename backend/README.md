# Backend — Sports-Predictions

API **FastAPI** para ingesta MLB, clima (Open-Meteo), predicción y persistencia en **PostgreSQL**. Visión y endpoints: [../docs/estatus-actual.md](../docs/estatus-actual.md).

## Instalación y arranque

```bash
pip install -e ".[dev]"
export DATABASE_URL=postgresql+asyncpg://...
# Crear tablas: ejecuta sql/001_initial_schema.sql en Supabase SQL Editor (ver sql/README.md)
uvicorn app.main:app --reload --app-dir src
```

- **Documentación interactiva:** `http://127.0.0.1:8000/docs`
- **Tests:** `pytest` desde este directorio
- **Lint:** `ruff check src tests`, `black src tests`, `isort src tests`, `mypy src`

## Pipeline Fases 1–3 (histórico, snapshots, entrenamiento)

Desde este directorio (`backend/`), con `DATABASE_URL` cargada:

1. **Ingesta MLB por rango de fechas** (no sintético):

   ```bash
   python -m app.cli.backfill_history --start 2025-03-20 --end 2025-04-15 --sleep 0.3
   ```

   Usa `--no-fetch-details` para ir más rápido (menos boxscore). Ajusta fechas al inicio de temporada deseado.

2. **Reconstruir `game_feature_snapshots`** (rachas + etiquetas en partidos finales):

   ```bash
   python -m app.cli.rebuild_feature_snapshots
   python -m app.cli.rebuild_feature_snapshots --season 2025 --window 10
   ```

3. **Entrenar modelo desde la BD** y escribir artifact:

   ```bash
   python -m app.ml.train_from_db --output src/app/ml/artifacts/model.joblib --val-from 2025-08-01 --model-version rf-db-v1
   ```

   Luego arranca el API con `ML_MODEL_PATH` apuntando a ese archivo (o copia el joblib sobre el `model.joblib` por defecto).

Orden detallado: ver `../../docs/PIPELINE_COMPLETO_TODO.md` (raíz del workspace Predictions).

## Rutas principales (prefijo `/api/v1` salvo `/health`)

| Ruta | Descripción breve |
|------|-------------------|
| `GET /games`, `GET /games/{game_pk}` | Partidos por fecha y detalle |
| `POST /games/{game_pk}/weather` | Clima Open-Meteo |
| `GET /mlb/teams`, `GET /mlb/history/games` | Equipos e historial |
| `POST /mlb/sync-range`, `POST /mlb/games/{game_pk}/sync` | Sincronización MLB |
| `GET /predict/{game_pk}` | Predicción ML |

Detalle completo: [../docs/estatus-actual.md](../docs/estatus-actual.md).
