# Despliegue: Supabase + Render + Vercel

## Supabase (PostgreSQL)

1. Crea un proyecto en [Supabase](https://supabase.com).
2. En **Project Settings → Database**, copia la cadena **Connection string** para `psycopg` o **URI** compatible con async.
3. Usa el pooler (puerto 6543) si Render lo recomienda para muchas conexiones; para SQLAlchemy async suele funcionar `postgresql+asyncpg://...`.

Variable en Render (y local):

- `DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DATABASE`
- `DATABASE_STATEMENT_TIMEOUT_SECONDS` (opcional, default en código **120**): evita que Postgres cancele `UPDATE` con `boxscore_json` muy grande por el `statement_timeout` corto del pooler (error `QueryCanceledError` / *canceling statement due to statement timeout*). Sube a **180** o **300** si aún falla en redes lentas.  
  Si la plataforma solo ofrece `postgresql://` (sin `+asyncpg`), puedes pegarla tal cual: el backend la normaliza a `postgresql+asyncpg://` para usar **asyncpg** (no hace falta instalar `psycopg2`).

4. **Crear el esquema (sin Alembic):** en Supabase abre **SQL** → **New query**, pega el contenido de [backend/sql/001_initial_schema.sql](../backend/sql/001_initial_schema.sql) y ejecuta. La referencia legible de tablas está en [backend/sql/schema.txt](../backend/sql/schema.txt).

   Cambios futuros: nuevos archivos `002_*.sql` en `backend/sql/`, actualizar `schema.txt`, y ejecutar solo el nuevo script en el SQL Editor.

## Render (API FastAPI)

1. **New → Web Service**, conecta el repositorio o sube el `Dockerfile` en `backend/`.
2. **Root directory**: `backend` (si el servicio solo construye el API).
3. **Docker** o **Build**: `pip install -e .` + `uvicorn` si no usas Docker.
4. **Start command** (sin Docker):

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT --app-dir src
```

5. Variables de entorno:

| Variable | Descripción |
|----------|-------------|
| `DATABASE_URL` | URL async de Supabase (ver arriba) |
| `CORS_ORIGINS` | Orígenes del front en Vercel, p. ej. `https://tu-app.vercel.app,http://localhost:4200` |
| `ML_MODEL_PATH` | Opcional; ruta al `model.joblib` si no usas el artefacto por defecto |
| `ADMIN_JWT_SECRET` | Obligatorio para el panel **Operaciones** (`/mlb/operaciones`): firma de la cookie de sesión |
| `ADMIN_BOOTSTRAP_SECRET` | Opcional, **solo** para crear el **primer** operador sin CLI (ver abajo); quitar tras usar |

6. La base ya debe tener las tablas creadas (paso Supabase anterior) antes de que el API escriba datos.

### Primer usuario del panel Operaciones

En `002_prediction_cache_and_admin.sql` **no** hay filas en `admin_users` (no commiteamos contraseñas).

1. Con **CLI** (shell en tu máquina o en Render, con `DATABASE_URL` apuntando a la misma BD):

```bash
cd backend && python3 -m app.cli.create_admin --username admin --password 'contraseña-segura'
```

2. Sin shell: define temporalmente `ADMIN_BOOTSTRAP_SECRET` (valor largo y aleatorio), despliega, y una sola vez:

```bash
curl -sS -X POST "$API_URL/api/v1/admin/auth/bootstrap" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Bootstrap-Secret: $ADMIN_BOOTSTRAP_SECRET" \
  -d '{"username":"admin","password":"contraseña-segura"}' -c /dev/null -v
```

(Respuesta con `Set-Cookie` si usas sesión por cookie; luego entra en `/mlb/operaciones` y haz login con ese usuario, o repite login desde el navegador.)

3. **Elimina `ADMIN_BOOTSTRAP_SECRET`** del entorno cuando ya exista al menos un operador (el endpoint deja de ser útil y reduce superficie de ataque).

Usuarios adicionales: solo `create_admin`.

## Vercel (Angular)

1. **Import project** en [Vercel](https://vercel.com).
2. **Root Directory** del proyecto:
   - Si el repo es solo `Sports-Predictions/`, deja **Root Directory** = `frontend` (o vacío si importaste solo esa carpeta).
   - Si el repo es la carpeta padre `Predictions/` con varios proyectos, pon **Root Directory** = `Sports-Predictions/frontend`.
3. **Framework Preset**: **Other** (o deja que detecte; si falla, Other).
4. **Install Command**: `npm install` (una sola; no pongas varios gestores a la vez).
5. **Build Command**: `npm run build` (producción; **no** uses `ng serve` en Vercel — es solo para desarrollo local).
6. **Output Directory**: **`dist/browser`** — obligatorio con el Angular application builder: los archivos estáticos (`index.html`, JS, CSS) están ahí. Si pones solo `dist` o otra ruta, obtendrás **404**.
7. El [vercel.json](../frontend/vercel.json) del repo fija `buildCommand`, `outputDirectory` y `rewrites` (SPA → `index.html`). Si el dashboard de Vercel tiene valores distintos, prioriza coherencia con ese archivo o edítalo en el repo.
8. **Environment**: ajusta `src/environments/environment.prod.ts` con la URL pública del API en Render (HTTPS).

### Si ves 404 en Vercel

| Causa típica | Qué hacer |
|--------------|-----------|
| Output Directory mal | Debe ser **`dist/browser`**, no `dist` ni `dist/frontend`. |
| Raíz del proyecto mal | El build debe ejecutarse donde está `package.json` del front (ver Root Directory arriba). |
| Rutas del router (refresh) | Confirma que existan `rewrites` a `/index.html` (ya en `vercel.json`). |
| `ng serve` como build | Incorrecto: solo sirve en local; en Vercel usa `npm run build`. |

## CORS

El backend ya usa `CORSMiddleware` con `CORS_ORIGINS` (coma-separada). Incluye el dominio de producción de Vercel exacto (sin barra final).

## Comprobación

- `GET https://<render-host>/health` → `{"status":"ok"}`
- `GET https://<render-host>/docs` → Swagger
- Front: abrir la URL de Vercel y comprobar listado de partidos con el backend en Render.

## Notas sobre el API (Sports-Predictions)

- **Sincronización:** el `POST /api/v1/mlb/sync-range` está acotado (máximo **7 días** por petición). El front del historial MLB pide **un día por llamada** encadenada; rangos largos implican varias peticiones secuenciales, no una sola megapetición.
- **Pooler Supabase:** usar la URL de **transaction pool** en `DATABASE_URL` desde Render si la red es IPv4-only; ver [errores_direct_connection.md](errores_direct_connection.md).
- **Documentación del proyecto:** [README.md](README.md) (índice de `docs/`) y [estatus-actual.md](estatus-actual.md) (endpoints y flujos).
