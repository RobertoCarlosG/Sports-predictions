# Caché HTTP en el frontend (Angular + RxJS)

> Estado: implementado en abril 2026. Ámbito: SPA Angular `frontend/`.
> Documento hermano (memoización dentro de componentes con `signal`/`computed`):
> [../../docs/ANGULAR-MEMOIZATION-GUIDE.md](../../docs/ANGULAR-MEMOIZATION-GUIDE.md).

## Objetivo

Reducir el **egress de Supabase** y la latencia percibida cuando el usuario alterna
entre vistas que pegan a los mismos datos (Hoy / Mañana / Semana, detalles de partido,
backtest). La idea: que la primera petición de cada combinación de parámetros se
comparta entre suscriptores y se replique sin nueva HTTP mientras siga siendo «fresca».

## Diseño en dos capas

1. **Caché de componente** — `Map<cacheKey, GamesListCacheEntry>` dentro de
   `GameListComponent`. Guarda el resultado **post-procesado** (juegos fusionados,
   meta consolidada, mapa de probabilidades). Vive mientras viva la instancia del
   componente; muere al navegar a otra ruta que destruya el componente.
2. **Caché de servicio** — `RequestCache<T>` con `shareReplay(1)` y TTL en
   `GamesApiService` y `AdminApiService`. Vive durante toda la sesión (services
   `providedIn: 'root'`). Sobrevive al cambio de ruta y a la destrucción del
   componente.

```mermaid
flowchart LR
  U[Usuario] --> C[Componente Angular]
  C -->|"api.listGames(...)"| S["GamesApiService<br/>singleton providedIn:'root'"]
  S --> H[HttpClient]
  H -->|HTTPS| B[Backend FastAPI]
  B --> DB[(Supabase / Postgres)]

  subgraph "Caché de componente"
    CC[("listCache (Map)<br/>datos fusionados<br/>+ predicciones aplicadas<br/>vive mientras vive el componente")]
  end

  subgraph "Caché de servicio - shareReplay(1)"
    SC1[("listGamesCache<br/>TTL 60 s")]
    SC2[("predictCache<br/>TTL 60 s")]
    SC3[("gameCache<br/>TTL 60 s")]
    SC4[("historyCache<br/>TTL 5 min")]
    SC5[("teamsCache<br/>TTL 1 h")]
    SC6[("backtestCache<br/>TTL 5 min - AdminApiService")]
  end

  C -. consulta antes que el servicio .-> CC
  S -. cada GET .-> SC1 & SC2 & SC3 & SC4 & SC5
```

## Flujo Hoy → Mañana → Hoy (caso feliz: 0 bytes en el regreso)

```mermaid
sequenceDiagram
  actor U as Usuario
  participant C as GameListComponent
  participant CC as listCache (componente)
  participant S as GamesApiService
  participant SC as listGamesCache (servicio)
  participant API as Backend → Supabase

  rect rgb(240, 248, 240)
    Note over U,API: 1) Abre "Hoy"
    U->>C: /mlb/today
    C->>CC: get("today")
    CC-->>C: miss
    C->>S: listGames("today")
    S->>SC: get("today|sync=true|p=true")
    SC-->>S: miss → factory()
    S->>API: GET /api/v1/games?date=today
    API-->>S: GamesListResponse
    S-->>SC: shareReplay almacena
    S-->>C: respuesta
    C->>CC: put("today", procesado)
  end

  rect rgb(240, 248, 240)
    Note over U,API: 2) Cambia a "Mañana"
    U->>C: /mlb/tomorrow
    C->>S: listGames("tomorrow")
    S->>SC: get("tomorrow|...")
    SC-->>S: miss → factory()
    S->>API: GET /api/v1/games?date=tomorrow
    API-->>S: respuesta
  end

  rect rgb(232, 245, 233)
    Note over U,API: 3) Vuelve a "Hoy" (dentro del TTL)
    U->>C: /mlb/today
    C->>CC: get("today")
    CC-->>C: HIT (instantáneo)
    Note right of API: 0 bytes a Supabase ✓
  end

  rect rgb(255, 248, 230)
    Note over U,API: 4) Si el componente fue destruido entre tanto<br/>(p. ej. /mlb/game/X y volver):<br/>la listCache desaparece pero la del servicio aguanta
    C->>CC: get("today")
    CC-->>C: miss (componente nuevo)
    C->>S: listGames("today")
    S->>SC: get("today|...")
    SC-->>S: HIT (TTL vivo)
    S-->>C: respuesta cacheada
    Note right of API: 0 bytes a Supabase ✓
  end
```

## Decisión interna de `RequestCache.get(key, factory, force)`

`frontend/src/app/services/request-cache.ts` implementa la utilidad reutilizable.
`shareReplay({ bufferSize: 1, refCount: false })` garantiza que peticiones
concurrentes con la misma clave compartan **una sola** HTTP. Los errores no se
cachean: la entrada se elimina al primer fallo y el siguiente subscriber lanza
una petición nueva.

```mermaid
flowchart TD
  Start["get(key, factory, force=false)"] --> Q1{force === true?}
  Q1 -->|sí| Del["entries.delete(key)"]
  Q1 -->|no| Q2
  Del --> Q2{entries.has(key)?}
  Q2 -->|no| Make
  Q2 -->|sí| Q3{"now − createdAt < ttlMs?"}
  Q3 -->|sí| Hit["return entry.observable<br/>(replay del último valor)"]
  Q3 -->|no| Make["factory().pipe(shareReplay(1))"]
  Make --> Save["entries.set(key, entry)"]
  Save --> Wrap["pipe(catchError → entries.delete(key))<br/>los errores no se cachean"]
  Wrap --> Out[return observable]
  Hit --> Out
```

## Botón «Actualizar» (force refresh desde la UI)

Disponible en:

- `GameListComponent` (Hoy/Mañana/Semana): header de la página → `forceReload()`.
- `MlbHistoryComponent`: toolbar al lado de «Filtros» → `forceReload()`.
- `BacktestDashboardComponent`: botón «Actualizar» → `refresh()`.

> Diferencia con los botones existentes en el detalle de partido y en operaciones:
> «Actualizar datos» (`GameDetailComponent`) y «Actualizar rango»
> (`MlbHistoryComponent`) son **mutaciones del backend** (descargan de la API de
> MLB y reescriben en BD). El botón «Actualizar» nuevo solo **vuelve a leer del
> backend** ignorando la caché del cliente; no toca MLB ni reescribe nada.

```mermaid
sequenceDiagram
  actor U as Usuario
  participant Btn as "Botón Actualizar"
  participant C as GameListComponent
  participant CC as listCache (componente)
  participant S as GamesApiService
  participant SC as listGamesCache (servicio)
  participant API as Backend → Supabase

  U->>Btn: clic
  Btn->>C: forceReload()
  C->>C: retry()  ➜ loadForDates(sel, {force:true})
  C->>CC: listCache.delete(cacheKey)
  C->>S: listGames(date, true, {force:true})
  S->>SC: get(key, factory, force=true)
  SC->>SC: entries.delete(key)
  SC->>SC: miss garantizado
  S->>API: GET /api/v1/games?date=...
  API-->>S: datos frescos
  S-->>SC: shareReplay re-pobla con TTL nuevo
  S-->>C: GamesListResponse
  C->>CC: put(cacheKey, procesado nuevo)
  C-->>U: vista actualizada
```

## Mutaciones invalidan caché automáticamente

Cualquier acción que pueda hacer **stale** los datos cacheados (sync con MLB,
recálculo de predicción, refresco de clima) invalida las entradas afectadas en
`tap(...)` dentro del propio servicio. Al volver el usuario a la lista o al
detalle, el `RequestCache.get` encuentra cache miss y trae los datos nuevos.

```mermaid
sequenceDiagram
  actor U as Admin / Usuario
  participant C as GameDetailComponent / Operations
  participant S as GamesApiService
  participant SC1 as listGamesCache
  participant SC2 as predictCache
  participant SC3 as gameCache
  participant SC4 as historyCache
  participant API as Backend

  alt syncMlbRange (Operations)
    C->>S: syncMlbRange({start, end})
    S->>API: POST /mlb/sync-range
    API-->>S: ok
    Note right of S: tap(...): limpia tres cachés
    S->>SC1: clear()
    S->>SC2: clear()
    S->>SC3: clear()
    S->>SC4: clear()
  else syncMlbGame(pk) (botón "Actualizar datos")
    C->>S: syncMlbGame(pk)
    S->>API: POST /mlb/games/{pk}/sync
    S->>SC3: invalidate(pk)
    S->>SC2: invalidate(pk)
    S->>SC1: clear()
  else refreshPrediction(pk) (botón "Actualizar estimación")
    C->>S: refreshPrediction(pk)
    S->>API: POST /predict/{pk}/refresh
    S->>SC2: invalidate(pk)
    S->>SC1: clear()
  else refreshWeather(pk)
    C->>S: refreshWeather(pk)
    S->>API: POST /games/{pk}/weather
    S->>SC3: invalidate(pk)
    S->>SC1: clear()
  end

  Note over C,API: La próxima visita a la lista o a otro detalle<br/>encuentra cache miss y trae los datos nuevos
```

> En `AdminApiService`, las mutaciones que pueden cambiar el modelo o los
> snapshots (`trainModel`, `rebuildSnapshots`, `clearPredictionCache`,
> `reloadModel`, `logout`) limpian `backtestCache`.

## Resumen visual: ¿cuándo viaja un byte a Supabase?

```mermaid
flowchart TD
  A[Usuario ejecuta una acción] --> B{¿Tipo de acción?}
  B -->|Navegar a Hoy/Mañana/Semana| C[listGames]
  B -->|Abrir detalle de partido| D[getGame + predict]
  B -->|Filtrar histórico| E[listMlbHistory]
  B -->|Backtest con mismas params| F[getBacktestReport]
  B -->|Botón Actualizar| G[force=true]
  B -->|Sync rango / partido / refrescar predicción| H[Mutación POST]

  C --> Q1{¿En cache de servicio<br/>y dentro de TTL?}
  D --> Q1
  E --> Q1
  F --> Q1

  Q1 -->|Sí| Hit["✅ HIT: 0 bytes a Supabase<br/>(replay del Observable)"]
  Q1 -->|No| Net["🌐 GET al backend → Supabase"]

  G --> Force["🌐 force borra entrada → GET fresco"]
  H --> Mut["🌐 POST + invalidación de cachés afectadas<br/>siguientes lecturas → GET fresco"]
```

## Tabla de TTL por endpoint

| Servicio / método | Caché | TTL | Invalidación automática |
|---|---|---|---|
| `GamesApiService.listGames(date, sync, {force})` | `listGamesCache` | 60 s | `syncMlbRange`, `syncMlbGame`, `refreshWeather`, `refreshPrediction` |
| `GamesApiService.getGame(pk, {force})` | `gameCache` | 60 s | `syncMlbGame`, `refreshWeather` (por pk) |
| `GamesApiService.predict(pk, {force})` | `predictCache` | 60 s | `syncMlbGame`, `refreshPrediction` (por pk) |
| `GamesApiService.listMlbTeams({force})` | `teamsCache` | 1 h | — |
| `GamesApiService.listMlbHistory(params, {force})` | `historyCache` | 5 min | `syncMlbRange` |
| `AdminApiService.getBacktestReport(params, {force})` | `backtestCache` | 5 min | `trainModel`, `rebuildSnapshots`, `clearPredictionCache`, `reloadModel`, `logout` |

## Archivos relevantes

- `frontend/src/app/services/request-cache.ts` — utilidad genérica con TTL + `shareReplay(1)`.
- `frontend/src/app/services/games-api.service.ts` — caché por endpoint + `tap` de invalidación.
- `frontend/src/app/services/admin-api.service.ts` — `backtestCache`.
- `frontend/src/app/game-list/game-list.component.ts` — `forceReload()` reusa `retry()` con `force: true`.
- `frontend/src/app/mlb-history/mlb-history.component.ts` — `forceReload()` → `load({ force: true })`.
- `frontend/src/app/backtest-dashboard/backtest-dashboard.component.ts` — `refresh()` → `load({ force: true })`.

## Cuándo NO usar el cache (decisiones tomadas)

- `AdminApiService.getBackfillStatus()`: lo poll cada 2 s durante un backfill;
  cachear no aporta y enmascararía el progreso.
- `AdminApiService.status()`: estado general del API; pequeño y se pide
  manualmente al pulsar «Refrescar estado».
- `AdminApiService.authReady()`, `checkSession()`, `login()`, `logout()`,
  `refreshSession()`: lifecycle de sesión; el estado se mantiene en
  `sessionOk` dentro del propio servicio.
- Mutaciones (`POST`/`PUT`/`DELETE`): por definición no se cachean. Su misión
  aquí es **invalidar** las entradas que dejan stale.

## Cómo añadir caché a un nuevo endpoint GET

1. En el servicio singleton, declara una instancia de `RequestCache<T>` con su TTL.
2. Envuelve el `this.http.get<T>(...)` en `cache.get(key, factory, options?.force)`.
3. Si hay un endpoint `POST` que muta los mismos datos, añade `tap(() => cache.invalidate(key))` o `cache.clear()` según el alcance.
4. Si el componente tiene un botón de refrescar, propaga `{ force: true }` al servicio.

## Bonus pendientes (opcionales)

- Mostrar un timestamp tipo «Última actualización: hace 12 s» junto al botón.
- Bajar el TTL de `listGamesCache` a ~15 s cuando la fecha sea «hoy» y haya
  partidos `Live`/`In Progress`, para refrescar marcadores en curso sin que el
  usuario tenga que pulsar el botón.
