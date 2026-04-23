"""Límite global de ráfagas para peticiones a statsapi.mlb.com (compartido entre requests y CLI)."""
from __future__ import annotations

import asyncio
import time


class MlbRateLimiter:
    """
    Tras `burst_size` peticiones, espera `cooldown_seconds` antes de abrir otra ráfaga.
    Por defecto: 5 llamadas y luego ~25 s de pausa (~10–12 peticiones/min en ráfagas).
    """

    def __init__(self, burst_size: int, cooldown_seconds: float) -> None:
        self._burst_size = max(1, burst_size)
        self._cooldown = max(0.0, cooldown_seconds)
        self._lock = asyncio.Lock()
        self._count = 0
        self._burst_start = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if self._count >= self._burst_size:
                elapsed = now - self._burst_start
                wait = max(0.0, self._cooldown - elapsed)
                if wait > 0:
                    await asyncio.sleep(wait)
                self._count = 0
            if self._count == 0:
                self._burst_start = time.monotonic()
            self._count += 1


_limiter: MlbRateLimiter | None = None


def get_mlb_rate_limiter() -> MlbRateLimiter | None:
    """Singleton según configuración; None si el límite está desactivado."""
    global _limiter
    from app.core.config import settings

    if settings.mlb_api_rate_limit_burst_size <= 0:
        return None
    if _limiter is None:
        _limiter = MlbRateLimiter(
            burst_size=settings.mlb_api_rate_limit_burst_size,
            cooldown_seconds=settings.mlb_api_rate_limit_cooldown_seconds,
        )
    return _limiter


def reset_mlb_rate_limiter_for_tests() -> None:
    global _limiter
    _limiter = None
