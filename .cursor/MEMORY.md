# Project memory — Sports-Predictions

Persistent facts and workflows for agents working in this repo.

## Validation gate (always)

Every change must be tested and proven with builds before the task is done:

- **Frontend**: `cd frontend && npm run build` (production config)
- **Backend**: `cd backend && pytest`
- Add or run unit tests when changing behavior; do not skip verification for "small" edits.

## Repo structure

- `backend/` — FastAPI, PostgreSQL, pytest, ML (Random Forest / XGBoost)
- `frontend/` — Angular 19, Material, output `dist/browser`
- Root `docs/` is gitignored; backend docs live in `backend/docs/`

## Frontend style budgets

Angular production `anyComponentStyle` error limit: **8 kB** per component. `operations.component.scss` was split: auth styles moved to `frontend/src/app/operations/operations-auth.global.scss` imported from `styles.scss`.

## Ops / local dev

- Backend: `uvicorn app.main:app --reload --app-dir src` from `backend/` with venv + `.env`
- Frontend: `npm start` from `frontend/`
- Admin user: `create-admin` CLI after `ADMIN_JWT_SECRET` in `.env`
