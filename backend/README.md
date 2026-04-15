# Backend

Install and run:

```bash
pip install -e ".[dev]"
export DATABASE_URL=postgresql+asyncpg://...
alembic upgrade head
uvicorn app.main:app --reload --app-dir src
```

Tests: `pytest` from this directory.

Lint: `ruff check src tests`, `black src tests`, `isort src tests`, `mypy src`.
