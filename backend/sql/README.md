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
