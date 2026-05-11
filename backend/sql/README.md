# Esquema SQL (sin Alembic)

La base se define y evoluciona con **archivos `.sql` versionados** en este directorio. No usamos Alembic: los cambios se aplican **a mano** en el **SQL Editor** de Supabase (o con `psql` contra tu `DATABASE_URL`).

**Este README** resume orden, verificación y alta de operadores. La referencia humana de columnas está en [`schema.txt`](schema.txt).

## Orden de aplicación

Aplicar **en este orden** (todas las migraciones son idempotentes):

1. `001_initial_schema.sql` — `teams`, `games`, `game_weather`, `game_feature_snapshots`.
2. `002_game_scores.sql` — añade `home_score`, `away_score` a `games`.
3. `002_prediction_cache_and_admin.sql` — `prediction_results`, `admin_users`.
4. `003_pitching_and_starters.sql` — abridores en `games`, ERAs en snapshots, `pitching_era_cache`.
5. `004_prediction_evaluation.sql` — campos para tracking de aciertos/fallos en `prediction_results`.
6. `005_teams_optimization.sql` — índice y comentarios para reducir lock contention en `teams`.
7. `006_model_versions.sql` — tabla `model_versions` (histórico + flag `is_active` único).

> Sí, hay dos archivos con prefijo `002_` (uno toca `games`, el otro crea tablas nuevas). Mantenidos por historia. Para nuevas migraciones, usar el siguiente número libre: **`007_`**.

## Cómo aplicarlas

### Supabase (recomendado)

1. Abre [Supabase](https://supabase.com) → tu proyecto → **SQL** → **New query**.
2. Pega el contenido del primer archivo, ejecuta.
3. Repite para los siguientes, en orden.
4. Tras aplicar `002_prediction_cache_and_admin.sql`, configura `ADMIN_JWT_SECRET` en el backend y crea el primer operador (ver más abajo).

### `psql` contra `DATABASE_URL`

```bash
cd backend
for f in sql/001_initial_schema.sql \
         sql/002_game_scores.sql \
         sql/002_prediction_cache_and_admin.sql \
         sql/003_pitching_and_starters.sql \
         sql/004_prediction_evaluation.sql \
         sql/005_teams_optimization.sql \
         sql/006_model_versions.sql; do
  echo ">>> $f"
  psql "$DATABASE_URL" -f "$f"
done
```

### Verificación rápida

```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema='public'
  AND table_name IN (
    'teams', 'games', 'game_weather', 'game_feature_snapshots',
    'pitching_era_cache', 'prediction_results', 'admin_users', 'model_versions'
  );
```

```bash
curl "$API_URL/api/v1/admin/auth/ready"
# → login_available: true significa JWT secret + admin_users OK.
```

## Referencia legible del esquema

- [`schema.txt`](schema.txt) — descripción de todas las tablas y columnas (fuente de verdad humana).
- Los archivos `.sql` son la fuente de verdad ejecutable.

## Panel «Operaciones» (`admin_users`)

No hay usuarios de ejemplo en el SQL (no se versionan contraseñas).

1. Aplicar `002_prediction_cache_and_admin.sql`.
2. En el backend, definir `ADMIN_JWT_SECRET` (mín. 16 caracteres en producción).
3. Crear el **primer** operador con **una** de estas opciones:

   - **CLI** (recomendado), desde `backend/` con `DATABASE_URL` cargada y tras `pip install -e ".[dev]"`:

     ```bash
     create-admin --username tu_usuario --password '...'
     ```

     Sin instalar el paquete:

     ```bash
     PYTHONPATH=src python3 -m app.cli.create_admin --username ... --password '...'
     ```

   - **Bootstrap HTTP** (solo si `admin_users` está vacío): definir `ADMIN_BOOTSTRAP_SECRET` y llamar:

     ```bash
     curl -X POST "$API_URL/api/v1/admin/auth/bootstrap" \
       -H "Content-Type: application/json" \
       -H "X-Admin-Bootstrap-Secret: $ADMIN_BOOTSTRAP_SECRET" \
       -d '{"username": "...", "password": "..."}'
     ```

     **Quitar `ADMIN_BOOTSTRAP_SECRET`** del entorno tras crear el primer usuario.

Para más operadores: solo CLI (`create-admin`).

## Convenciones para nuevas migraciones

1. Nombre `<NN>_<descripcion-corta>.sql`. Próximo número libre: `007_`.
2. Idempotentes (`IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, etc.).
3. `COMMENT ON COLUMN` cuando el nombre no sea obvio.
4. Sincronizar en el mismo cambio: este `README`, `schema.txt` y los modelos SQLAlchemy en `src/app/models/mlb.py`.
5. Probar contra una BD vacía siguiendo la lista de aplicación de arriba.
