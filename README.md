# Sports-Predictions

Monorepo del **dashboard y API** del MVP **Sports-Predictions**: **MLB primero** (datos oficiales [statsapi.mlb.com](https://statsapi.mlb.com)), clima de estadio (**Open-Meteo**), predicciones con **Random Forest** (`joblib`). La arquitectura admite ampliar a fútbol/NBA u otras fuentes en fases posteriores.

## Qué incluye este MVP

| Capa | Entregado |
|------|-----------|
| **API (FastAPI)** | Partidos por fecha y detalle, sync con MLB (rango acotado y por `game_pk`), historial, equipos, clima, predicción `/predict/{game_pk}` |
| **Datos** | PostgreSQL: partidos, equipos, marcadores, JSON de box score, alineaciones (live o derivadas del box score en partidos finalizados) |
| **Web (Angular)** | Listado por fecha, historial MLB (sync por rango día a día), detalle con box score legible, botones de actualizar clima y sincronizar un partido |
| **Ops** | DDL en `backend/sql/`, despliegue documentado (Supabase + Render + Vercel) |

**Documentación del proyecto (visión, alcance, estado, despliegue):** carpeta **[docs/](docs/README.md)** — empezar por [docs/vision-y-alcance.md](docs/vision-y-alcance.md) y [docs/estatus-actual.md](docs/estatus-actual.md). Las reglas de estilo del workspace padre siguen en `../docs/` (p. ej. [estilo-programacion.md](../docs/estilo-programacion.md)); no se duplican aquí.

## Layout del repositorio

| Path | Descripción |
|------|-------------|
| `backend/` | FastAPI, SQLAlchemy 2 async, PostgreSQL, pytest |
| `frontend/` | Angular, build estática en `dist/browser` |
| `docs/` | Visión, estado, despliegue, pendientes, errores de conexión |

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

Ver [docs/deploy.md](docs/deploy.md) (Supabase, Render, Vercel, CORS, salida de build **`dist/browser`** en Vercel).

## Conventions

Conventional commits (`feat:`, `fix:`, …), ramas `feature/`, `bugfix/`, `docs/`, TDD en backend. Detalles de estilo: documentación en `../docs/`.
