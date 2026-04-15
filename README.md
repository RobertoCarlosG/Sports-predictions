# Sports-Predictions

Monorepo for the sports dashboard MVP: **MLB** first (statsapi.mlb.com, Open-Meteo, ML predictions), then soccer/NBA.

## Layout

| Path | Description |
|------|-------------|
| `backend/` | FastAPI, SQLAlchemy 2 async, PostgreSQL, pytest |
| `frontend/` | Angular dashboard |
| `docs/` | Project status and roadmap (see also parent `../docs/` for shared conventions) |

Parent folder `Predictions/docs/` holds cross-project rules ([estilo-programacion.md](../docs/estilo-programacion.md), [contexto-general.md](../docs/contexto-general.md)). Do not duplicate those rules here; follow them when contributing.

## Quick start (local)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
# Set DATABASE_URL to a local PostgreSQL instance, then:
alembic upgrade head
uvicorn app.main:app --reload --app-dir src
```

API: `http://127.0.0.1:8000` — docs at `/docs`.

### Frontend

```bash
cd frontend
npm install
npm start
```

App: `http://localhost:4200` — configure `src/environments/environment.development.ts` with the backend URL.

## Deployment

See [docs/deploy.md](docs/deploy.md) for Supabase (PostgreSQL), Render (API), and Vercel (Angular). Frontend build output: `frontend/dist/frontend/browser`.

## Conventions

Conventional commits (`feat:`, `fix:`, …), branches `feature/`, `bugfix/`, `docs/`, TDD on backend. See parent documentation for full style rules.
