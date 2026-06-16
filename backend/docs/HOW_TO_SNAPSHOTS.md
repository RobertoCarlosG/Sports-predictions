# Cómo ejecutar snapshots de indicadores

`game_feature_snapshots` almacena las estadísticas rodantes (rachas de victorias, ERA de pitchers, datos meteorológicos, etc.) que alimentan al modelo de predicción. Este documento cubre todos los escenarios habituales.

---

## Referencia rápida de endpoints

| Escenario | Endpoint | Body de ejemplo |
|---|---|---|
| Importar datos históricos | `POST /api/v1/admin/pipeline/backfill` | `{ "start_date": "2025-03-20", "end_date": "2025-04-20" }` |
| Reconstruir todos los snapshots | `POST /api/v1/admin/pipeline/rebuild-snapshots` | `{}` |
| Reconstruir una temporada | `POST /api/v1/admin/pipeline/rebuild-snapshots` | `{ "season": "2025" }` |
| Reconstruir rango de fechas | `POST /api/v1/admin/pipeline/rebuild-snapshots` | `{ "start_date": "2025-06-01", "end_date": "2025-06-07" }` |
| Entrenar modelo | `POST /api/v1/admin/pipeline/train` | `{}` |
| Recargar modelo en memoria | `POST /api/v1/admin/model/reload` | (sin body) |
| ETL diario completo (hoy + mañana) | `POST /api/v1/admin/pipeline/mlb-daily-snapshot` | (sin body) |

Todos los endpoints requieren autenticación. Ver la sección [Autenticación](#autenticación) al final.

---

## Escenario 1 — Desde cero (DB vacía)

Orden obligatorio cuando la base de datos no tiene datos históricos:

### Paso 1: Importar datos históricos

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/admin/pipeline/backfill \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "X-Requested-With: XMLHttpRequest" \
  -d '{"start_date": "2024-03-20", "end_date": "2025-06-13"}'
```

```bash
# Via CLI (más rápido para rangos largos)
cd backend
python -m app.cli.backfill_history \
  --start 2024-03-20 \
  --end 2025-06-13 \
  --sleep 0.5
```

El parámetro `--sleep` (segundos entre requests) evita superar el rate-limit de la API de MLB.

### Paso 2: Recalcular snapshots de indicadores

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/admin/pipeline/rebuild-snapshots \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "X-Requested-With: XMLHttpRequest" \
  -d '{}'
```

```bash
# Via CLI
python -m app.cli.rebuild_feature_snapshots
# Con ventana rodante personalizada (default: 10 partidos)
python -m app.cli.rebuild_feature_snapshots --window 15
```

### Paso 3: Entrenar el modelo

```bash
curl -X POST http://localhost:8000/api/v1/admin/pipeline/train \
  -H "Authorization: Bearer <TOKEN>" \
  -H "X-Requested-With: XMLHttpRequest"
```

### Paso 4: Recargar el modelo en memoria

```bash
curl -X POST http://localhost:8000/api/v1/admin/model/reload \
  -H "Authorization: Bearer <TOKEN>" \
  -H "X-Requested-With: XMLHttpRequest"
```

---

## Escenario 2 — Solo unos días específicos

Útil cuando se corrigieron datos de un rango concreto o se necesita actualizar un período puntual sin tocar el resto de la historia.

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/admin/pipeline/rebuild-snapshots \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "X-Requested-With: XMLHttpRequest" \
  -d '{"start_date": "2025-06-01", "end_date": "2025-06-07"}'
```

```bash
# Via CLI
python -m app.cli.rebuild_feature_snapshots --start 2025-06-01 --end 2025-06-07
```

> **Nota:** cuando se especifica un rango de fechas, el servicio carga todo el histórico anterior para calcular las rachas rodantes correctamente, pero solo borra y reescribe snapshots dentro del rango indicado.

---

## Escenario 3 — Actualizar los últimos N días

```bash
# Via CLI (--last-days N calcula el rango automáticamente)
python -m app.cli.rebuild_feature_snapshots --last-days 7

# Via API (alternativa)
N=7
START=$(date -v -${N}d +%Y-%m-%d)   # macOS
# START=$(date -d "-${N} days" +%Y-%m-%d)  # Linux
END=$(date +%Y-%m-%d)

curl -X POST http://localhost:8000/api/v1/admin/pipeline/rebuild-snapshots \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "X-Requested-With: XMLHttpRequest" \
  -d "{\"start_date\": \"$START\", \"end_date\": \"$END\"}"
```

---

## Escenario 4 — Forzar reconstrucción completa de una temporada

El endpoint siempre sobreescribe: primero borra los snapshots del rango/temporada afectada y luego los recalcula. No hay flag `force` porque el comportamiento ya es destructivo-por-diseño.

```bash
# Reconstruir toda la temporada 2025
curl -X POST http://localhost:8000/api/v1/admin/pipeline/rebuild-snapshots \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "X-Requested-With: XMLHttpRequest" \
  -d '{"season": "2025", "window": 10}'
```

```bash
# Via CLI
python -m app.cli.rebuild_feature_snapshots --season 2025 --window 10
```

---

## Escenario 5 — Verificar qué fechas tienen snapshots

### Opción A — CLI (recomendado)

```bash
# Resumen por temporada
python -m app.cli.snapshot_status

# Solo una temporada
python -m app.cli.snapshot_status --season 2025

# Ver también qué fechas concretas faltan
python -m app.cli.snapshot_status --season 2025 --show-missing
```

Salida de ejemplo:

```
==================================================================
  TEMPORADA    JUEGOS   SNAPS  FALTAN  DESDE        HASTA
==================================================================
  2024           2430    2430       0  2024-03-20   2024-09-29
  2025            812     805       7  2025-03-18   2025-06-13  ←
==================================================================

  Último snapshot : 2025-06-06
  Último juego    : 2025-06-13
  Desfase         : 7 día(s) sin snapshot

  Fechas con juegos finales SIN snapshot (3 días):
    2025-06-07  temporada=2025  juegos=8
    2025-06-08  temporada=2025  juegos=7
    2025-06-09  temporada=2025  juegos=6
```

### Cómo interpretar la salida y qué hacer

> **Importante:** `FALTAN` = total de juegos sin snapshot de cualquier status (Final, Scheduled, Postponed…).
> `--show-missing` desglosa esos juegos en dos grupos para que sepas exactamente qué requiere acción.

#### Caso A — Hay "Juegos FINALES sin snapshot"

```
  Juegos FINALES sin snapshot — necesitan rebuild (3 días):
    2025-06-07  juegos=8  (Final)
    2025-06-08  juegos=7  (Final)
    2025-06-09  juegos=6  (Final)
```

Estos sí requieren acción: el snapshot se corrió antes de que terminaran esos partidos (o no se corrió ese día). Reconstruir solo ese rango:

```bash
curl -X POST http://localhost:8000/api/v1/admin/pipeline/rebuild-snapshots \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "X-Requested-With: XMLHttpRequest" \
  -d '{"start_date": "2025-06-07", "end_date": "2025-06-09"}'
```

Volver a correr `snapshot_status --show-missing` para confirmar que desapareció la sección de finales.

#### Caso B — Solo hay "Juegos NO finales sin snapshot"

```
  2026          1481    1466      15  2026-02-20   2026-06-14  ←

  Sin juegos finales pendientes de snapshot.

  Juegos NO finales sin snapshot — 15 registros (no requieren acción inmediata):
    2026-06-14  juegos=12  (Scheduled)
    2026-06-14  juegos=3   (In Progress)
```

No hay nada que hacer: son partidos de hoy que todavía no terminaron, o partidos suspendidos/aplazados de días anteriores. El ETL diario los capturará cuando finalicen.

Si necesitas actualizar hoy sin esperar al ETL nocturno:

```bash
curl -X POST http://localhost:8000/api/v1/admin/pipeline/mlb-daily-snapshot \
  -H "Authorization: Bearer <TOKEN>" \
  -H "X-Requested-With: XMLHttpRequest"
```

Si ves juegos con status `Postponed` de varios días atrás, son partidos aplazados que se jugarán en otra fecha — no requieren snapshot hasta que se reprogramen y finalicen.

#### Caso C — `FALTAN` es 0 en todas las temporadas

Todo al día. No se requiere acción.

### Opción B — SQL directo (requiere acceso a Supabase o psql)

```sql
-- Resumen por temporada
SELECT g.season,
       COUNT(g.game_pk)                              AS total_games,
       COUNT(gfs.game_pk)                            AS with_snapshot,
       COUNT(g.game_pk) - COUNT(gfs.game_pk)        AS missing,
       MIN(g.game_date)                              AS first_date,
       MAX(g.game_date)                              AS last_date
FROM games g
LEFT JOIN game_feature_snapshots gfs ON gfs.game_pk = g.game_pk
GROUP BY g.season
ORDER BY g.season;

-- Fechas sin snapshot (juegos finales sin indicadores)
SELECT g.game_date, g.season, COUNT(*) AS n
FROM games g
LEFT JOIN game_feature_snapshots gfs ON gfs.game_pk = g.game_pk
WHERE gfs.game_pk IS NULL
  AND g.status ILIKE '%final%'
GROUP BY g.game_date, g.season
ORDER BY g.game_date;
```

> **Advertencia Supabase:** en el plan free el egress está limitado. Usar consultas agregadas, no `SELECT *` sobre tablas grandes.

---

## Escenario 6 — Flujo completo para una temporada nueva

```bash
# 1. Importar toda la temporada nueva (ej. 2026)
curl -X POST http://localhost:8000/api/v1/admin/pipeline/backfill \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "X-Requested-With: XMLHttpRequest" \
  -d '{"start_date": "2026-03-20", "end_date": "2026-04-30"}'

# 2. Reconstruir snapshots de la temporada completa
curl -X POST http://localhost:8000/api/v1/admin/pipeline/rebuild-snapshots \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "X-Requested-With: XMLHttpRequest" \
  -d '{"season": "2026"}'

# 3. Re-entrenar el modelo con los nuevos datos
curl -X POST http://localhost:8000/api/v1/admin/pipeline/train \
  -H "Authorization: Bearer <TOKEN>" \
  -H "X-Requested-With: XMLHttpRequest"

# 4. Verificar que el modelo cargó correctamente
curl http://localhost:8000/api/v1/admin/status \
  -H "Authorization: Bearer <TOKEN>"

# 5. Recargar en memoria
curl -X POST http://localhost:8000/api/v1/admin/model/reload \
  -H "Authorization: Bearer <TOKEN>" \
  -H "X-Requested-With: XMLHttpRequest"
```

---

## Parámetros de rebuild-snapshots

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `season` | `string \| null` | `null` | Temporada a reconstruir (ej. `"2025"`). `null` = todas las temporadas. |
| `window` | `int` (1-50) | `10` | Partidos anteriores usados para calcular la racha rodante. |
| `start_date` | `YYYY-MM-DD \| null` | `null` | Fecha inicio del rango. Requiere también `end_date`. |
| `end_date` | `YYYY-MM-DD \| null` | `null` | Fecha fin del rango. Requiere también `start_date`. |

> `start_date`/`end_date` tienen **prioridad** sobre `season`: si se especifican ambos, el filtro por season se ignora.

---

## Autenticación

Todos los endpoints de `/api/v1/admin/*` requieren:

```bash
# Obtener token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/admin/auth/login \
  -H "Content-Type: application/json" \
  -H "X-Requested-With: XMLHttpRequest" \
  -d '{"username": "admin", "password": "tu_password"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

# Luego incluir en cada request:
# -H "Authorization: Bearer $TOKEN"
# -H "X-Requested-With: XMLHttpRequest"   ← requerido en POST/PUT/DELETE
```

---

## CLI disponibles

Todos se ejecutan desde el directorio `backend/` con `uv run python -m <comando>`.

### Pipeline principal

| Comando | Equivalente en panel | Descripción |
|---|---|---|
| `python -m app.cli.backfill_history --start YYYY-MM-DD --end YYYY-MM-DD [--sleep 0.5]` | Importar fechas | Importa histórico de MLB día a día |
| `python -m app.cli.rebuild_feature_snapshots [--season 2026] [--window 10]` | Recalcular indicadores | Recalcula snapshots por temporada |
| `python -m app.cli.rebuild_feature_snapshots --start YYYY-MM-DD --end YYYY-MM-DD` | Recalcular indicadores | Recalcula snapshots en rango de fechas |
| `python -m app.cli.rebuild_feature_snapshots --last-days N` | Recalcular indicadores | Recalcula los últimos N días |
| `python -m app.ml.train_from_db [--season 2026] [--algorithm xgb]` | Entrenar modelo | Reentrena el modelo desde `game_feature_snapshots` |
| `python -m app.cli.clear_prediction_cache` | Limpiar caché | Vacía `prediction_results` para forzar recalcular |
| `python -m app.cli.daily_snapshot` | ETL diario | Sync hoy+mañana + rebuild snapshots de la temporada |
| `python -m app.cli.fix_fifty [--season 2026]` | Arreglar predicciones al 50% | Rebuild temporada actual + vaciar caché |

> **Nota sobre "Recargar modelo":** este botón cambia el estado en memoria del servidor en Render y **no tiene equivalente CLI local**. No es necesario: el servidor detecta cambios en `model.joblib` automáticamente en el siguiente request tras un re-entrenamiento.

### Auditoría y utilidades

| Comando | Descripción |
|---|---|
| `python -m app.cli.snapshot_status [--season 2026] [--show-missing]` | **Audita cobertura de snapshots y fechas que faltan** |
| `python -m app.cli.calibrate [--model-version rf-db-v1]` | Ajusta calibración de probabilidades |
| `python -m app.cli.create_admin` | Crea usuario del panel admin |
