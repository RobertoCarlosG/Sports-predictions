"""Límite global de ráfagas para peticiones a statsapi.mlb.com (compartido entre requests y CLI)."""
from __future__ import annotations

import asyncio
import time


class MlbRateLimiter:
    """
    Tras `burst_size` peticiones, espera `cooldown_seconds` antes de otra ráfaga.

    El `asyncio.sleep` ocurre **fuera** del lock: varias coroutines pueden avanzar
    en paralelo (p. ej. `asyncio.gather` sobre partidos) sin serializar cada HTTP.

    Defaults vía `Settings` (p. ej. ~20 ráfaga / 1 s pausa); 0 burst = desactivado.
    """

    def __init__(self, burst_size: int, cooldown_seconds: float) -> None:
        self._burst_size = max(1, burst_size)
        self._cooldown = max(0.0, cooldown_seconds)
        self._lock = asyncio.Lock()
        self._count = 0
        self._burst_start = 0.0

    async def acquire(self) -> None:
        while True:
            wait_time = 0.0
            async with self._lock:
                now = time.monotonic()
                if self._count >= self._burst_size:
                    elapsed = now - self._burst_start
                    wait_time = max(0.0, self._cooldown - elapsed)
                    if wait_time <= 0:
                        self._count = 0
                        continue
                else:
                    self._count += 1
                    if self._count == 1:
                        self._burst_start = time.monotonic()
                    return
            await asyncio.sleep(wait_time)
            async with self._lock:
                self._count = 0


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
