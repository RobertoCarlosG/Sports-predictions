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

## Rutas principales (prefijo `/api/v1` salvo `/health`)

| Ruta | Descripción breve |
|------|-------------------|
| `GET /games`, `GET /games/{game_pk}` | Partidos por fecha y detalle |
| `POST /games/{game_pk}/weather` | Clima Open-Meteo |
| `GET /mlb/teams`, `GET /mlb/history/games` | Equipos e historial |
| `POST /mlb/sync-range`, `POST /mlb/games/{game_pk}/sync` | Sincronización MLB |
| `GET /predict/{game_pk}` | Predicción ML |

Detalle completo: [../docs/estatus-actual.md](../docs/estatus-actual.md).
