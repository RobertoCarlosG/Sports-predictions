import collections
import time
from fastapi import Request, HTTPException

_api_rate_limits: dict[str, list[float]] = collections.defaultdict(list)
API_MAX_REQUESTS = 15
API_WINDOW_SECONDS = 60

async def rate_limit_public_api(request: Request) -> None:
    """
    Limitador de tasa básico por IP en memoria para endpoints públicos costosos.
    Máximo 30 peticiones por minuto por IP.
    """
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    attempts = _api_rate_limits[ip]
    attempts[:] = [t for t in attempts if now - t < API_WINDOW_SECONDS]
    if len(attempts) >= API_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="Límite de peticiones excedido. Por favor espera.")
    attempts.append(now)
