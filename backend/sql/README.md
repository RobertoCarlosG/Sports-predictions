# Esquema SQL (sin Alembic)

La base se define y evoluciona con **archivos `.sql` versionados** en este directorio. No usamos Alembic: los cambios se aplican **a mano** en el **SQL Editor** de Supabase (o con `psql` contra tu `DATABASE_URL`).

## Orden recomendado

1. Abre [Supabase](https://supabase.com) → tu proyecto → **SQL** → **New query**.
2. Copia y ejecuta el contenido de `001_initial_schema.sql` (solo en bases vacías o la primera vez).
3. Para cambios posteriores, añade `002_nombre_descriptivo.sql`, documenta en `schema.txt` y ejecuta el nuevo script en el mismo editor.

## Referencia legible

- **[schema.txt](schema.txt)** — descripción de tablas y columnas (fuente de verdad humana).
- **`001_initial_schema.sql`** — DDL equivalente para Postgres/Supabase.

Tras crear tablas, configura `DATABASE_URL` en el backend (asyncpg) como siempre.

## Panel «Operaciones» (`admin_users`)

No hay usuarios de ejemplo en el SQL (no se versionan contraseñas).

1. Aplica también `002_prediction_cache_and_admin.sql` (tabla `admin_users`).
2. En el API, define `ADMIN_JWT_SECRET`.
3. Crea el **primer** operador con **una** de estas opciones:
   - **CLI** (recomendado): desde `backend/`, con `DATABASE_URL` en `.env` y tras `pip install -e .`:  
     `create-admin --username tu_usuario --password '...'`  
     (sin instalar: `PYTHONPATH=src python3 -m app.cli.create_admin --username ... --password '...'`)
   - **Bootstrap HTTP** (solo si `admin_users` está vacío): variable `ADMIN_BOOTSTRAP_SECRET`, luego  
     `POST /api/v1/admin/auth/bootstrap` con header `X-Admin-Bootstrap-Secret` y cuerpo `{"username","password"}`.  
     Quitar `ADMIN_BOOTSTRAP_SECRET` del entorno después del alta.

Más usuarios: solo CLI (`create_admin`).
