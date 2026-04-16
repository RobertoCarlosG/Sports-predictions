from __future__ import annotations

from fastapi import Request


def cors_headers_for_request(request: Request, cors_origins: str) -> dict[str, str]:
    """Cabeceras CORS para orígenes permitidos (p. ej. respuestas de error con JSON)."""
    origin = request.headers.get("origin")
    allowed = [o.strip() for o in cors_origins.split(",") if o.strip()]
    if not allowed:
        allowed = ["http://localhost:4200"]
    if origin and origin in allowed:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        }
    return {}
