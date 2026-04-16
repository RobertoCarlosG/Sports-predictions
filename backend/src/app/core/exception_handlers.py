from __future__ import annotations

import logging
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError

from app.core.config import settings
from app.core.cors_utils import cors_headers_for_request

logger = logging.getLogger(__name__)


def _error_payload(
    *,
    detail: str,
    message: str,
    technical: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "detail": detail,
        "message": message,
    }
    if technical and (settings.debug or detail == "database_schema_missing"):
        body["technical"] = technical
    return body


def _json_error(
    request: Request,
    *,
    status_code: int,
    detail: str,
    message: str,
    technical: str | None = None,
) -> JSONResponse:
    headers = cors_headers_for_request(request, settings.cors_origins)
    return JSONResponse(
        status_code=status_code,
        content=_error_payload(detail=detail, message=message, technical=technical),
        headers=headers,
    )


async def programming_error_handler(request: Request, exc: ProgrammingError) -> JSONResponse:
    logger.exception("ProgrammingError: %s", exc)
    text = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
    if "does not exist" in text.lower() and (
        "relation" in text.lower() or "table" in text.lower() or "undefinedtable" in text.lower()
    ):
        return _json_error(
            request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database_schema_missing",
            message=(
                "No existen las tablas en PostgreSQL. Ejecuta el script "
                "`backend/sql/001_initial_schema.sql` en el SQL Editor de Supabase "
                "(o tu instancia)."
            ),
            technical=text,
        )
    return _json_error(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="database_error",
        message="Error al consultar la base de datos.",
        technical=text,
    )


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("SQLAlchemyError: %s", exc)
    orig = getattr(exc, "orig", None)
    text = str(orig) if orig is not None else str(exc)
    return _json_error(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="database_error",
        message="Error al consultar la base de datos.",
        technical=text,
    )

