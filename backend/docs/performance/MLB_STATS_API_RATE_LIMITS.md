# MLB Stats API (`statsapi.mlb.com`) — límites y práctica

## Documentación oficial

- MLB expone la API pública **sin API key** para datos de estadísticas; **no publica un límite numérico de peticiones por segundo** en la documentación orientada a desarrolladores de contenido.
- El uso esperado es razonable (scraping masivo agresivo no recomendado).

## Ecosistema comunitario

Herramientas populares (`pybaseball`, wrappers tipo **MLB-StatsAPI**) realizan **muchas solicitudes secuenciales o en lotes** durante importaciones de datos sin documentar un techo fijo; la práctica habitual es limitar concurrencia para no saturar la red propia, no porque MLB devuelva sistemáticamente `429` a bajo volumen.

## Prueba empírica recomendada (I1)

Desde el repo, con variables `MLB_API_RATE_LIMIT_*` ajustadas:

1. Ejecutar tráfico sostenido (p. ej. 5 / 15 / 30 RPS) durante 60 s contra endpoints de solo lectura (`/schedule`, `/game/{pk}/boxscore`).
2. Registrar: latencia p50/p95, conteo de `429`, `5xx`, timeouts.

Si no aparecen `429` hasta decenas de RPS, un **throttle interno muy bajo** (p. ej. ráfagas de 5 con pausas largas) es el cuello de botella de la aplicación, no la API externa.

## Configuración en este proyecto

- `MLB_API_RATE_LIMIT_BURST_SIZE`, `MLB_API_RATE_LIMIT_COOLDOWN_SECONDS` en [`.env.example`](../../.env.example) y [`app/core/config.py`](../../src/app/core/config.py).
- El limitador **no duerme bajo lock global** (permite paralelismo real con `asyncio.gather`).
