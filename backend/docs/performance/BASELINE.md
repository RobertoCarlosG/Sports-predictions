# Baseline de rendimiento (I3)

Metodología reproducible antes/después de optimizaciones.

## Entorno

- Fecha de muestra de MLB Stats API: `2026-04-28` (schedule de temporada).
- Comando (solo red, sin BD): desde `backend/`:

```bash
python profile_mlb.py
```

## Resultados registrados

| Medición | Valor | Notas |
|----------|-------|--------|
| `GET /schedule` (schedule hydrated) | ~0.48 s | `profile_mlb.py`; primera llamada a statsapi.mlb.com |
| Sync completo día (`sync_games_for_date`, `fetch_details=true`) | *(requiere PostgreSQL local)* | Ejecutar `python profile_sync.py` con `DATABASE_URL` válido |

## GET `/api/v1/games` (integración)

Con el servidor en marcha:

```bash
curl -s -o /dev/null -w "%{time_total}\n" \
  "http://127.0.0.1:8000/api/v1/games?date=2026-04-28&sync=true&fetch_details=true&include_predictions=true"
```

Registrar `time_total` y número de partidos del día en la respuesta JSON (`games.length`).
