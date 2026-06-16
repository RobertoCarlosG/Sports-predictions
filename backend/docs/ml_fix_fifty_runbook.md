# Runbook: predicciones atascadas en ~50%

Guía para cuando un partido (o todos) muestran una probabilidad de victoria ~50%.

## Por qué pasa (en una línea)

El modelo (`rf-db-v1`) está bien. El 50% sale porque el **vector de entrada es simétrico**:
local y visitante reciben valores idénticos, así que el Random Forest no tiene con qué
inclinarse. La predicción de hoy **no depende de los datos de hoy**, depende del
**histórico previo** de cada equipo (sus últimos ~10 partidos finalizados).

Hay dos causas:

- **Caso A — falta el snapshot del partido.** No se corrió el rebuild para esa fecha, así
  que `features.py` inyecta todas las constantes simétricas (0.5/0.5, 4.5/4.5, ERA 4.5/4.2).
- **Caso B — el historial es demasiado corto.** El snapshot existe, pero cada equipo tiene
  0-1 partidos finalizados previos en la BD, así que las rachas caen al default `(0.5, 4.5)`
  para ambos lados. Pasa cuando solo se importaron unos pocos días.

Cuando se rellena con constantes, la API marca `defaults_injected: true` y la UI muestra el
aviso **"Datos insuficientes — predicción no fiable"**. Úsalo como señal rápida.

---

## Paso 0 — Diagnosticar antes de actuar

```bash
cd backend
uv run python -m app.cli.snapshot_status --season 2026 --show-missing
```

Mira el "Desfase" (días sin snapshot) y la lista de juegos finales sin snapshot.

Para un partido concreto, revisa `defaults_injected` en la respuesta de la API
(`GET /api/v1/games/{game_pk}` → `prediction.defaults_injected`) o el badge en la UI.
Si quieres ver los valores crudos, consulta `game_feature_snapshots` para ese `game_pk`:
- No hay fila → **Caso A**.
- `home_wins_roll` y `away_wins_roll` ambos `0.5` **y** `home_runs_avg_roll`/`away_runs_avg_roll`
  ambos `4.5` → **Caso B** (faltan finales previos).

---

## Paso 1 — Decidir el camino

| Síntoma | Camino |
|---|---|
| Snapshot ausente o desfase de pocos días, pero ya hay histórico cargado | **Caso A** → atajo rápido |
| Casi ningún equipo tiene partidos previos; importaste pocos días | **Caso B** → backfill profundo primero |

---

## Caso A — atajo rápido (lo más común)

**Desde el panel admin (Operaciones):** botón **"Arreglar predicciones al 50%"**.
Hace en un paso: recalcular indicadores de la temporada actual (con ERA real) → vaciar caché
de estimaciones → recargar el modelo.

**Equivalente por API:**
```
POST /api/v1/admin/pipeline/rebuild-snapshots   { "season": "2026" }
POST /api/v1/admin/pipeline/clear-prediction-cache
POST /api/v1/admin/model/reload
```

**Equivalente por CLI:**
```bash
cd backend
uv run python -m app.cli.rebuild_feature_snapshots --season 2026
# luego limpiar caché + recargar desde el panel/endpoints de arriba
```

Recarga el partido: la probabilidad ya no debería ser ~50% y el badge debe desaparecer.
**Si sigue en 50% → es Caso B**, falta histórico previo.

---

## Caso B — backfill profundo (cuando falta histórico)

### B.1 — Calcular el rango

La ventana rodante es de **10 partidos** (`rolling_window=10` en `feature_snapshots.py`).
Para que cada equipo tenga rachas reales necesitas ~10 finales previos:

- `start` = opening day de la temporada en curso (recomendado), o como mínimo `hoy − 30 días`.
- `end` = hoy.

> Nota egress Supabase (incidente conocido): usa `--sleep` y un rango acotado para no
> disparar el consumo del free tier.

### B.2 — Importar histórico

```bash
cd backend
uv run python -m app.cli.backfill_history --start 2026-03-27 --end 2026-06-14 --sleep 0.5
```

(Sustituye las fechas por tu rango real.)

### B.3 — Recalcular indicadores

```bash
uv run python -m app.cli.rebuild_feature_snapshots --season 2026
```

Imprescindible: sin esto las rachas siguen en 0.5/4.5.

### B.4 — (Opcional) Reentrenar

Solo si agregaste muchos finales nuevos y quieres que el modelo aprenda de ellos:

```bash
uv run python -m app.ml.train_from_db --season 2026
```

Luego `POST /api/v1/admin/model/reload` (o el botón "Recargar RF en memoria").

### B.5 — Limpiar caché y verificar

```
POST /api/v1/admin/pipeline/clear-prediction-cache
```

Recarga un partido y confirma que `home_win_probability` ya no es ~0.5 y que
`defaults_injected` es `false` (el badge desaparece).

---

## Resumen mental

> 50% = features simétricas = "no tengo datos para diferenciar a estos equipos".
> El arreglo es **darle datos**: snapshots recalculados (Caso A) o histórico profundo + rebuild (Caso B).
