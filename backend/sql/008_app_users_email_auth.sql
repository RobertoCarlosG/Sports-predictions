-- 008_app_users_email_auth.sql
-- Agrega soporte para login email+contraseña a la tabla app_users.
-- google_id pasa a ser nullable para permitir usuarios que se registren con email.

ALTER TABLE app_users
  ALTER COLUMN google_id DROP NOT NULL;

ALTER TABLE app_users
  ADD COLUMN IF NOT EXISTS password_hash VARCHAR(256);

-- Cada usuario debe tener al menos un método de autenticación
ALTER TABLE app_users
  DROP CONSTRAINT IF EXISTS chk_app_users_auth_method;

ALTER TABLE app_users
  ADD CONSTRAINT chk_app_users_auth_method
  CHECK (google_id IS NOT NULL OR password_hash IS NOT NULL);
