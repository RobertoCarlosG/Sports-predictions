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
# Crear tablas: ejecuta `backend/sql/001_initial_schema.sql` en Supabase (ver `backend/sql/README.md`)
uvicorn app.main:app --reload --app-dir src
```

API: `http://127.0.0.1:8000` — docs at `/docs`.

### Frontend

```bash
cd frontend
npm install
npm start
```

App: `http://localhost:4200` — el API por defecto está en `src/environments/environment.ts` (`apiUrl`).

### VS Code (depurar / ejecutar)

Abre la carpeta **`Predictions`** (la que contiene `Sports-Predictions/`) como workspace. En **Run and Debug** elige:

- **Sports-Predictions: Backend (FastAPI)** — requiere extensión **Python** + `debugpy`, y el archivo `backend/.env` (copia desde `.env.example`).
- **Sports-Predictions: Frontend (Angular)** — `npm run start` en `frontend/`.
- **Sports-Predictions: Backend + Frontend** — arranca ambos a la vez.

Si abres solo `Sports-Predictions/` como raíz del workspace, las rutas de `../.vscode/launch.json` no coinciden: usa los comandos de arriba o duplica/ajusta el `launch.json` local.

## Deployment

See [docs/deploy.md](docs/deploy.md) for Supabase (PostgreSQL), Render (API), and Vercel (Angular). Frontend build output: `frontend/dist/frontend/browser`.

## Conventions

Conventional commits (`feat:`, `fix:`, …), branches `feature/`, `bugfix/`, `docs/`, TDD on backend. See parent documentation for full style rules.
