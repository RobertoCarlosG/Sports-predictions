import collections
import time

from fastapi import HTTPException, Request

from app.core.config import settings

# Por IP, en memoria (cada worker Uvicorn tiene su propio contador).
_api_rate_limits_read: dict[str, list[float]] = collections.defaultdict(list)
_api_rate_limits_write: dict[str, list[float]] = collections.defaultdict(list)


def _apply_limit_for_bucket(
    ip: str,
    attempts: list[float],
    max_requests: int,
    window_seconds: int,
) -> None:
    now = time.time()
    attempts[:] = [t for t in attempts if now - t < window_seconds]
    if len(attempts) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail="Límite de peticiones excedido. Por favor espera.",
        )
    attempts.append(now)


async def rate_limit_public_read(request: Request) -> None:
    """GET públicos (lista juegos, predict, detalle): cupo más alto."""
    ip = request.client.host if request.client else "unknown"
    _apply_limit_for_bucket(
        ip,
        _api_rate_limits_read[ip],
        settings.api_rate_limit_read_max_requests,
        settings.api_rate_limit_window_seconds,
    )


async def rate_limit_public_write(request: Request) -> None:
    """POST costosos (sync MLB, refresh predicción, clima): cupo más bajo."""
    ip = request.client.host if request.client else "unknown"
    _apply_limit_for_bucket(
        ip,
        _api_rate_limits_write[ip],
        settings.api_rate_limit_write_max_requests,
        settings.api_rate_limit_window_seconds,
    )


async def rate_limit_public_api(request: Request) -> None:
    """Alias retrocompatible: mismo cupo que escritura costosa."""
    await rate_limit_public_write(request)
