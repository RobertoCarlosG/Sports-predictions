"""Verifica que los endpoints admin NBA (Fase C1) están registrados (sin DB)."""

from __future__ import annotations

from app.main import app


def _openapi_paths() -> set[str]:
    return set(app.openapi()["paths"].keys())


def test_reload_nba_route_registered() -> None:
    assert "/api/v1/admin/model/reload-nba" in _openapi_paths()


def test_nba_rebuild_snapshots_route_registered() -> None:
    assert "/api/v1/admin/pipeline/nba-rebuild-snapshots" in _openapi_paths()
