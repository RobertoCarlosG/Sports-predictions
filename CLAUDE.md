# Sports-Predictions — Claude instructions

Monorepo: `backend/` (FastAPI + pytest) and `frontend/` (Angular 19).

## Verify every change

Do not finish a task without running the checks that match your edits:

```bash
# Frontend (required for any frontend change)
cd frontend && npm run build

# Frontend unit tests (when logic/templates changed)
cd frontend && npm test -- --no-watch --browsers=ChromeHeadless

# Backend (required for any backend change)
cd backend && pytest
```

Report which commands you ran and their outcome. Fix failures before handing off.

## Project layout

- `backend/src/app/` — API, services, ML, CLI
- `backend/tests/` — pytest (unit + integration)
- `frontend/src/app/` — Angular components and services
- `backend/sql/` — DDL scripts (run in order)

## Conventions

- Conventional commits: `feat:`, `fix:`, `refactor:`, etc.
- Backend: async SQLAlchemy 2, `ruff` + `black` per `pyproject.toml`
- Frontend: Angular Material, SCSS with design tokens in `src/_tokens.scss` and glass mixins in `src/_glass.scss`
- Minimize scope — match existing patterns; no drive-by refactors

## Frontend build notes

Production build uses strict budgets in `frontend/angular.json`. Component SCSS is capped at 8 kB (`anyComponentStyle`). Large style blocks should live in global SCSS or child components, not oversized single component files.
