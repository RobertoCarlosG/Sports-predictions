# Sports-Predictions

Monorepo del **dashboard y API** del MVP **Sports-Predictions**: **MLB primero** (datos oficiales [statsapi.mlb.com](https://statsapi.mlb.com)), clima de estadio (**Open-Meteo**), predicciones con **Random Forest** (`joblib`). La arquitectura admite ampliar a fútbol/NBA u otras fuentes en fases posteriores.

## Qué incluye este MVP

| Capa | Entregado |
|------|-----------|
| **API (FastAPI)** | Partidos por fecha y detalle, sync con MLB (rango acotado y por `game_pk`), historial, equipos, clima, predicción `/predict/{game_pk}` |
| **Datos** | PostgreSQL: partidos, equipos, marcadores, JSON de box score, alineaciones (live o derivadas del box score en partidos finalizados) |
| **Web (Angular)** | Listado por fecha, historial MLB (sync por rango día a día), detalle con box score legible, botones de actualizar clima y sincronizar un partido |
| **Ops** | DDL en `backend/sql/`; Supabase / Render / Vercel cuando los configures por entorno |

La entrada **`/docs/`** del [`.gitignore`](.gitignore) hace que cualquier carpeta `docs/` en la **raíz del repositorio no forme parte del historial de Git** (equivalente a no publicar esa ruta con el código).

Las reglas de estilo del **workspace padre** (fuera de este monorepo) pueden seguir tu convención en `Predictions/`; no las duplicamos aquí.

## Layout del repositorio

| Path | Descripción |
|------|-------------|
| `backend/` | FastAPI, SQLAlchemy 2 async, PostgreSQL, pytest |
| `frontend/` | Angular, build estática en `dist/browser` |

(Repositorio: la raíz `docs/` está excluida por `.gitignore`; no se muestra en esta tabla.)

## Quick start (local)

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
# Set DATABASE_URL a tu PostgreSQL local, luego:
# Crear tablas: ejecuta `backend/sql/001_initial_schema.sql` y `002_prediction_cache_and_admin.sql`
# (ver `backend/sql/README.md`).
# Panel Operaciones: en .env pon ADMIN_JWT_SECRET y crea el primer usuario (tras pip install -e ".[dev]"):
#   create-admin --username admin --password 'tu-seguro'
#   # o: PYTHONPATH=src python3 -m app.cli.create_admin --username admin --password '...'
# (o bootstrap HTTP una vez; ver backend/sql/README.md).
uvicorn app.main:app --reload --app-dir src
```

API: `http://127.0.0.1:8000` — documentación interactiva en `/docs`.

### Frontend

```bash
cd frontend
npm install
npm start
```

App: `http://localhost:4200` — el API por defecto está en `src/environments/environment.ts` (`apiUrl`).

### VS Code (depurar / ejecutar)

Abre la carpeta **`Predictions`** (la que contiene `Sports-Predictions/`) como workspace. En **Run and Debug**:

- **Sports-Predictions: Backend (FastAPI)** — requiere extensión **Python** + `debugpy`, y `backend/.env`.
- **Sports-Predictions: Frontend (Angular)** — `npm run start` en `frontend/`.
- **Sports-Predictions: Backend + Frontend** — arranca ambos.

Si abres solo `Sports-Predictions/` como raíz del workspace, las rutas de `../.vscode/launch.json` pueden no coincidir: usa los comandos de arriba o ajusta un `launch.json` local.

## Despliegue

Patrón habitual: Postgres (p. ej. Supabase transaction pooler con `postgresql+asyncpg`), API en Render u otro host, frontend estático en Vercel con *Output Directory* `dist/browser`, y `CORS_ORIGINS` apuntando al origen web. Consulta variables en `backend/.env.example`.

## Conventions

Conventional commits (`feat:`, `fix:`, …), ramas `feature/` o `bugfix/`, tests en backend. Estilo de código según herramientas del repo (`ruff`, `black`, TypeScript strict en el front).
