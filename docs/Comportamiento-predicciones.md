# Lineamientos de visualización: predicciones y resultados

**Estado del documento:** vigente · alineado con `main` el 7 de mayo de 2026.
**Responsables:** Engineering Lead & Product Owner.

---

## 1. Objetivo

Definir la lógica de visualización de los partidos en el frontend según su temporalidad y la disponibilidad de datos. El fin es asegurar que el usuario entienda qué partidos fueron analizados, cuáles acertaron/fallaron y cuáles son simples registros históricos sin predicción.

## 2. Matriz de estados de visualización (UI/UX)

El componente de visualización en Angular sigue esta jerarquía. **Estado actual del producto:** todos los escenarios A-D están soportados por `match-card` y `game-detail`.

| Escenario | Condición | Elementos a mostrar | Estilo UI |
| :--- | :--- | :--- | :--- |
| **A. Partido futuro (con predicción)** | `game_date > hoy` && `prediction != null` | Probabilidad de victoria, marcador estimado, O/U, clima | Card resaltada, badge "Predicción lista" |
| **B. Partido futuro (sin análisis)** | `game_date > hoy` && `prediction == null` | Información básica del partido (equipos / hora) | Estado neutral, marca "Sin predicción" |
| **C. Partido pasado (con predicción)** | `game_date <= hoy` && `prediction.is_correct != null` | Resultado real **vs** predicción + Hit/Miss + % confianza | Borde verde (acierto) o rojo (fallo) |
| **D. Partido pasado (sin predicción)** | `game_date <= hoy` && `prediction == null` | Solo resultado real | Estilo neutral / gris |

> **Limitación conocida (verificar)**: el caso D depende de que la lógica `_compute_or_cache_prediction` en `backend/src/app/api/routes/games.py` saltó el cálculo para partidos pasados sin caché previa. Si el partido finalizó antes de que existiera modelo o de que el ETL lo hubiera procesado, queda sin predicción. Es comportamiento intencionado para no inventar predicciones a posteriori.

---

## 3. Lógica de negocio y métricas

### 3.1 Verificación de acierto (Hit/Miss)

**Backend** lo calcula y persiste tras cada sync de partidos finales (`prediction_cache.py::evaluate_predictions_for_final_games`).

- **HIT:** `is_correct = true` (es decir, `predicted_winner == actual_winner`).
- **MISS:** `is_correct = false`.
- **Pendiente:** `is_correct = null` (todavía no evaluado o partido sin marcador).

`predicted_winner` se deriva siempre de `home_win_probability`:

- `> 0.5` → `"home"`
- `<= 0.5` → `"away"`

Esto garantiza que la UI nunca tenga inconsistencia entre la barra de probabilidad y el lado predicho.

### 3.2 Porcentaje de efectividad

- **Por partido** (`match-card`): muestra el `% de probabilidad` del lado predicho.
- **Global** (`/operations` → tab Dashboard, `backtest-dashboard`): el endpoint `GET /admin/predictions/backtest` devuelve `BacktestSummary` con `n_games`, `ml_wins/losses`, `ou_wins/losses/pushes`, `global_hit_rate_pct` (combinado ML + O/U sobre picks decididos) y `total_decided_picks` / `total_correct_picks`. La serie temporal `BacktestTimePoint` permite graficar la evolución por día.
- **Métricas resumen** (`GET /admin/predictions/metrics`): `total_predictions`, `total_evaluated`, `total_correct`, `total_incorrect`, `accuracy_percentage`, `pending_evaluation`.

---

## 4. Especificaciones técnicas

### 4.1 Contrato de datos real

El backend devuelve estos modelos (`backend/src/app/schemas/games.py`):

```ts
// frontend/src/app/models/game.ts
export interface GameDetail {
  game_pk: number;
  season: string;
  game_date: string;       // YYYY-MM-DD
  status: string;          // "Scheduled", "Final", "Game Over", "Postponed", ...
  home_team: TeamOut;
  away_team: TeamOut;
  home_score?: number | null;
  away_score?: number | null;
  venue_id: number | null;
  venue_name: string | null;
  lineups: Record<string, unknown> | null;
  boxscore: Record<string, unknown> | null;
  weather: Record<string, unknown> | null;
  prediction?: PredictionOut | null;   // GET /games?include_predictions=true
}

export interface PredictionOut {
  game_pk: number;
  home_win_probability: number;          // 0..1
  total_runs_estimate: number;
  over_under_line: number;
  model_version: string;                  // p. ej. "rf-db-v1@a8b3f2"
  predicted_winner?: 'home' | 'away' | null;
  actual_winner?: 'home' | 'away' | 'tie' | null;
  is_correct?: boolean | null;
  evaluated_at?: string | null;           // ISO 8601
}
```

> **Nota histórica**: una versión anterior de este doc proponía un DTO `GameDisplayDTO` con `predicted_score` (home/away). El backend nunca expuso eso; lo que sí expone es `total_runs_estimate` (suma) y `over_under_line`. La UI calcula la "tendencia" de marcador a partir de la probabilidad y de los runs totales, sin desagregar por equipo.

### 4.2 Flujo de datos en la lista del día

`GET /api/v1/games?date=YYYY-MM-DD&include_predictions=true` devuelve:

```ts
interface GamesListResponse {
  games: GameDetail[];
  meta: GamesListMeta;
}

interface GamesListMeta {
  warnings: string[];                 // p. ej. snapshots faltantes
  info: string[];                     // p. ej. modelo no cargado
  missing_snapshot_count: number;     // partidos sin game_feature_snapshots
}
```

El frontend muestra los `warnings` con `friendly-error-banner` cuando son críticos (faltan indicadores → P(home) plana).

### 4.3 Caché y refresco

- **Servidor**: tabla `prediction_results` versionada por `model_version`. Se sirve si coincide con el modelo cargado; si no, se recalcula con `POST /predict/{pk}/refresh` o automáticamente.
- **Cliente**: `RequestCache` con `shareReplay(1)` + TTL (60 s para listados/predicciones, 5 min para historial, 1 h para teams). Vacíado tras mutaciones (sync, refresh).

---

## 5. Sugerencias y mejoras pendientes

- **Badge de diferencia** en partidos finalizados: mostrar la desviación entre el `total_runs_estimate` y `home_score + away_score`. _(no implementado todavía)_
- **Aviso de baja confianza**: si `max(p_home, 1-p_home) < 0.55`, mostrar el badge en gris con tooltip "Baja confianza". _(no implementado)_
- **Tooltip técnico**: explicar que la predicción usa Random Forest sobre indicadores rodantes, clima y ERA. Útil para transparencia. _(no implementado)_
- **Identificación del modelo**: hoy el `model_version` se ve en `GET /` y `/admin/status`, pero no en la app pública. PR2 añadirá un footer / banner discreto con `rf-db-v{n}` y métricas básicas. Ver [estado-real-mvp1.md](estado-real-mvp1.md) §M1.

---

## 6. Notas técnicas y limitaciones

- **`UPCOMING_SNAPSHOT_DAYS = 1`**: la vista `week` (lunes-domingo) muestra partidos a 3-7 días que no tienen snapshot → P(home) ≈ 0.5. La lista trae `meta.warnings` con la causa pero la UI todavía no la convierte en banner claro. Pendiente.
- **Caso D**: hoy se renderiza igual que un resultado MLB estándar; no se distingue visualmente del caso C cuando éste tampoco tiene predicción evaluada. _(verificación pendiente)_
- **Reentrenamiento manual**: cuando un nuevo modelo se promueve (`/admin/pipeline/train` + `/admin/model/reload`), las predicciones cacheadas con la versión anterior dejan de servir y se recalculan en lecturas. Para re-evaluar el histórico en bloque: `POST /admin/predictions/recompute-ml-evaluations`.
