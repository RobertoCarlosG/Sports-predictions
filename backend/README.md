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

### Sincronización diaria (snapshots) y evaluación ML

- En producción, activa `MLB_DAILY_SNAPSHOT_ENABLED=true` para que, cada noche a la hora UTC configurada (por defecto 03:00), el API importe el calendario MLB de **hoy y mañana** (según reloj UTC) y ejecute `rebuild_game_feature_snapshots` de la temporada en curso.
- Tras desplegar una corrección de evaluación, llama `POST /api/v1/admin/predictions/recompute-ml-evaluations` (panel Operaciones, autenticado) para recalcular `is_correct` del Moneyline en `prediction_results`.

## Indicadores y entrenamiento en local (BD del servidor)

Puedes ejecutar en tu máquina los mismos pasos que el panel **Operaciones**, pero contra la **misma** PostgreSQL que usa producción (solo cambia dónde corre el proceso).

1. En `backend/`, apunta `DATABASE_URL` a la instancia remota (Supabase/Render, **transaction pooler** + `+asyncpg` si aplica; mismo string que en el servidor).
2. (Opcional) `export ML_MODEL_PATH=…` si quieres fijar dónde se escribe el `joblib` al entrenar.
3. **Recalcular indicadores** (equivale a «Recalcular indicadores» en el panel; necesita alcanzar la API MLB desde tu red):

   ```bash
   python -m app.cli.rebuild_feature_snapshots --season 2026 --window 10
   ```

   Omite `--season` para recalcular todas las filas; más lento. Necesitas salida a internet a `statsapi.mlb.com` (ERA de abridores/staff vía caché).

4. **Entrenar** y dejar el artefacto en tu disco:

   ```bash
   python -m app.ml.train_from_db --output src/app/ml/artifacts/model.joblib --model-version rf-db-v1
   ```

5. **Subir y sustituir** en el despliegue: copia el `model.joblib` (SCP, panel de almacenamiento, imagen Docker, etc.) donde el API espera el modelo y define `ML_MODEL_PATH` a esa ruta, o **POST** `/api/v1/admin/model/reload` con sesión admin si el archivo ya está en el servidor. Reinicia el servicio si el binario se copió en build time.

Nunca abras la BD a `0.0.0.0` sin reglas; usa credenciales del proveedor y, si hace falta, IP allowlist o VPN.

### Si no hay ETL diario (snapshots no se generan solos)

El panel **no programa cron**: los `game_feature_snapshots` existen tras **importar** y pulsar **Recalcular indicadores**, o al ejecutar el CLI `rebuild_feature_snapshots`. Flujo mínimo provisional:

1. **Backfill** (Operaciones o `app.cli.backfill_history`) → filas en `games`.
2. **Rebuild snapshots** (Operaciones o `python -m app.cli.rebuild_feature_snapshots --season AAAA --window 10`) → rellena `game_feature_snapshots` leyendo `games` en orden; requiere salida a MLB API para ERAs en caché.
3. **Entrenar** y sustituir el `joblib` en el despliegue; **Recargar modelo** en el API.

**Subir el modelo vía Git (provisional):** en este repo, `*.joblib` bajo `artifacts/` está en `.gitignore` salvo `model.joblib` (excepción explícita). Puedes copiar tu `model.joblib` entrenado a `backend/src/app/ml/artifacts/model.joblib` y `git add -f` solo ese fichero, o usar **Git LFS** si supera un tamaño cómodo. Vuelve a desplegar el servicio que copia el artefacto en la imagen/ disco.

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
