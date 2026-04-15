# Backend

Install and run:

```bash
pip install -e ".[dev]"
export DATABASE_URL=postgresql+asyncpg://...
# Crear tablas: ejecuta sql/001_initial_schema.sql en Supabase SQL Editor (ver sql/README.md)
uvicorn app.main:app --reload --app-dir src
```

Tests: `pytest` from this directory.

Lint: `ruff check src tests`, `black src tests`, `isort src tests`, `mypy src`.
