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
8. `007_app_users_and_bets.sql` — `app_users`, `bet_banks`, `bet_periods`, `bets` (control de apuestas).
9. `008_app_users_email_auth.sql` — login email+contraseña en `app_users` (`password_hash`, `google_id` nullable).
10. `009_teams_league_division.sql` — `league` / `division` en `teams` + backfill de los 30 equipos.
11. `010_prediction_defaults_injected.sql` — `defaults_injected` en `prediction_results`.
12. `011_nba_core.sql` — `nba_teams`, `nba_games` (esquema NBA; vacío si `NBA_ENABLED=false`).
13. `012_nba_features_predictions.sql` — `nba_game_feature_snapshots`, `nba_prediction_results`.

> Sí, hay dos archivos con prefijo `002_` (uno toca `games`, el otro crea tablas nuevas). Mantenidos por historia. Para nuevas migraciones, usar el siguiente número libre: **`013_`**.

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
         sql/006_model_versions.sql \
         sql/007_app_users_and_bets.sql \
         sql/008_app_users_email_auth.sql \
         sql/009_teams_league_division.sql \
         sql/010_prediction_defaults_injected.sql \
         sql/011_nba_core.sql \
         sql/012_nba_features_predictions.sql; do
  echo ">>> $f"
  psql "$DATABASE_URL" -f "$f"
done
```

Con Docker local (`backend/docker-compose.yml`):

```bash
docker compose exec -T db psql -U sports -d sports_predictions -v ON_ERROR_STOP=1 < "$f"
```

### Verificación rápida

```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema='public'
  AND table_name IN (
    'teams', 'games', 'game_weather', 'game_feature_snapshots',
    'pitching_era_cache', 'prediction_results', 'admin_users', 'model_versions',
    'app_users', 'bet_banks', 'bet_periods', 'bets',
    'nba_teams', 'nba_games', 'nba_game_feature_snapshots', 'nba_prediction_results'
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

1. Nombre `<NN>_<descripcion-corta>.sql`. Próximo número libre: `013_`.
2. Idempotentes (`IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, etc.).
3. `COMMENT ON COLUMN` cuando el nombre no sea obvio.
4. Sincronizar en el mismo cambio: este `README`, `schema.txt` y los modelos SQLAlchemy (`src/app/models/mlb.py`, `nba.py`).
5. Probar contra una BD vacía siguiendo la lista de aplicación de arriba.
