# Auditoría de Seguridad — Backend Sports Predictions
**Modelo:** Claude Sonnet 4.6  
**Fecha:** 21 de junio de 2026  
**Alcance:** Revisión completa del código fuente en `backend/src/` — autenticación, autorización, lógica de negocio, manejo de secretos, integraciones externas y configuración de infraestructura.  
**Metodología:** Lectura completa de todos los archivos Python; análisis de flujos de datos; verificación cruzada entre capas (rutas → dependencias → servicios → modelos).

---

## Resumen ejecutivo

Se identificaron **10 vulnerabilidades confirmadas** y **3 hallazgos de nivel bajo**. Ninguna credencial de producción está en el repositorio git (el `.env` está correctamente ignorado). Sin embargo, hay fallos de diseño en autorización, gestión de sesiones y exposición de información que pueden ser explotados por usuarios legítimos malintencionados o por atacantes externos que obtengan un token de sesión.

Los hallazgos más críticos son: (1) la capa de autorización de usuarios no verifica si la cuenta está activa en la base de datos, y (2) un usuario desactivado puede reactivarse a sí mismo a través de Google OAuth.

| Severidad | Cantidad |
|-----------|---------|
| 🔴 Alta   | 3       |
| 🟡 Media  | 6       |
| 🔵 Baja   | 3       |

---

## Hallazgos de Severidad Alta

---

### A-01 · Bypass de desactivación de usuario — JWT sin verificación de `is_active`

**Archivo:** `src/app/api/deps_user.py:39–44`  
**Confianza:** 0.97

**Código vulnerable:**
```python
async def require_user_id(request, authorization) -> uuid.UUID:
    ...
    sub = decode_access_token(token, settings.user_jwt_secret)
    return uuid.UUID(sub)   # ← solo valida firma/expiración, no consulta la BD
```

**Descripción:**  
La dependencia `require_user_id` — usada en todos los endpoints de apuestas (`GET /bets`, `POST /bets`, `PATCH /bets/{id}`, etc.) — únicamente verifica la firma criptográfica y la expiración del JWT. No realiza ninguna consulta a la base de datos. En contraste, el endpoint `GET /auth/me` (`user_auth.py:312–315`) sí consulta la BD y verifica `user.is_active`.

Esta asimetría crea una brecha: si un administrador desactiva una cuenta (`is_active = False`), la sesión JWT del usuario (con TTL de 7 días por defecto, `config.py:87`) sigue siendo válida para todas las operaciones de apuestas.

**Escenario de explotación:**  
1. Usuario `A` crea apuestas fraudulentas o abusa del sistema.
2. El administrador desactiva la cuenta: `is_active = False`.
3. El usuario `A` conserva su cookie JWT y puede continuar creando, modificando y consultando apuestas durante hasta 7 días.
4. `/auth/me` rechaza correctamente la sesión, pero todas las rutas `/bets/*` siguen funcionando.

**Remediación:**
```python
# deps_user.py — añadir consulta a BD
async def require_user_id(request, authorization) -> uuid.UUID:
    ...
    uid = uuid.UUID(decode_access_token(token, settings.user_jwt_secret))
    # Verificar que el usuario existe y está activo
    async with async_session_factory() as session:
        user = await session.get(AppUser, uid)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Cuenta no disponible.")
    return uid
```
Alternativamente, reducir el TTL de usuario a ≤ 60 minutos y usar refresh tokens.

---

### A-02 · Reactivación de cuenta desactivada mediante Google OAuth

**Archivo:** `src/app/services/user_auth.py:29–35`  
**Confianza:** 0.95

**Código vulnerable:**
```python
async def upsert_app_user_from_google_profile(session, *, google_id, email, ...):
    result = await session.execute(select(AppUser).where(AppUser.google_id == google_id))
    user = result.scalar_one_or_none()
    if user is None:
        result2 = await session.execute(select(AppUser).where(AppUser.email == email))
        existing = result2.scalar_one_or_none()
        if existing is not None:
            existing.google_id = google_id
            existing.is_active = True   # ← FUERZA reactivación sin verificar estado previo
```

**Descripción:**  
Cuando un usuario con cuenta de email existente inicia sesión por primera vez con Google OAuth (vinculación de cuentas), la función `upsert_app_user_from_google_profile` establece incondicionalmente `is_active = True`. Esto ocurre también si la cuenta fue explícitamente desactivada por un administrador.

Incluso si la cuenta ya tiene `google_id` asignado (línea 50: `user.is_active = True`), el mismo patrón se repite en el "upsert" de logins subsecuentes de Google.

**Escenario de explotación:**  
1. El administrador desactiva al usuario `adversario@example.com` (`is_active = False`).
2. El usuario abre `GET /auth/google` → completa el flujo OAuth con Google.
3. `upsert_app_user_from_google_profile` se ejecuta con su email → establece `is_active = True`.
4. El usuario recibe un JWT válido y opera con normalidad.

El administrador no puede desactivar permanentemente a usuarios con acceso a una cuenta Google del mismo email sin eliminar la fila de base de datos.

**Remediación:**
```python
if existing is not None:
    if not existing.is_active:
        raise HTTPException(status_code=403, detail="Cuenta desactivada.")
    existing.google_id = google_id
    # NO modificar is_active
```

---

### A-03 · Fuga incondicional de nombres de tablas PostgreSQL en respuestas de error

**Archivo:** `src/app/core/exception_handlers.py:26`  
**Confianza:** 0.94

**Código vulnerable:**
```python
def _error_payload(*, detail, message, technical=None):
    body = {"detail": detail, "message": message}
    if technical and (settings.debug or detail == "database_schema_missing"):
        body["technical"] = technical  # ← expone texto crudo de PostgreSQL
    return body
```

**Descripción:**  
La condición `detail == "database_schema_missing"` actúa como un segundo interruptor para exponer el campo `technical`, que contiene el mensaje de error original de PostgreSQL como:

```
relation "admin_users" does not exist
LINE 1: SELECT id FROM admin_users LIMIT 1
```

Esta información se devuelve en la respuesta HTTP a cualquier cliente, **independientemente de que `DEBUG=false`**. El objetivo original era facilitar el diagnóstico en producción, pero cualquier cliente puede provocar este error invocando un endpoint que consulte una tabla inexistente.

**Escenario de explotación:**  
Un atacante llama a `GET /api/v1/admin/auth/ready` en una instancia con esquema incompleto. La respuesta incluye el nombre exacto de la tabla interna, el esquema PostgreSQL, y a veces el fragmento SQL que falló. Con esta información puede construir ataques más precisos u obtener inteligencia sobre la arquitectura de datos.

**Remediación:**
```python
# Remover la excepción para database_schema_missing:
if technical and settings.debug:
    body["technical"] = technical
```
Usar únicamente el mensaje amigable (`message`) en producción.

---

## Hallazgos de Severidad Media

---

### M-01 · Rate limiter de login administrativo inefectivo en despliegues multi-worker

**Archivos:** `src/app/api/routes/admin.py:103–114`, `src/app/api/deps_rate_limit.py:9–10`  
**Confianza:** 0.92

**Código vulnerable:**
```python
# admin.py — módulo de estado, por proceso Uvicorn
_login_attempts: dict[str, list[float]] = collections.defaultdict(list)
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 60
```

**Descripción:**  
El rate limiter de login de administrador y el de endpoints públicos son diccionarios Python en memoria, inicializados a nivel de módulo. En producción con Uvicorn multi-worker (`--workers 4`, configuración habitual en Render/Heroku) o Gunicorn, cada proceso tiene su propio diccionario independiente.

- Con **N workers**, el límite efectivo es `5 × N` intentos por ventana de 60 segundos.
- Un reinicio del proceso/pod (frecuente en plataformas PaaS) reinicia el contador a cero.
- Un atacante puede forzar la distribución entre workers mediante múltiples conexiones concurrentes.

**Escenario de explotación:**  
Con 4 workers: 20 intentos de fuerza bruta cada 60 segundos. Si la contraseña del administrador tiene 8 caracteres alfanuméricos, esto permite un ataque de diccionario a ritmo razonable. El reinicio del pod cada hora (plataformas free tier) vuelve a dar 20 intentos frescos.

**Remediación:**  
Mover el estado del rate limiter a un almacén compartido (Redis, Memcached) o a la base de datos. Como solución rápida, reducir `LOGIN_MAX_ATTEMPTS` a 3 y añadir backoff exponencial con bloqueo temporal de cuenta.

---

### M-02 · Secretos de aplicación expuestos en el subproceso de entrenamiento ML

**Archivo:** `src/app/api/routes/admin.py:645–653`  
**Confianza:** 0.90

**Código vulnerable:**
```python
proc = subprocess.run(
    cmd,
    cwd=str(BACKEND_ROOT),
    capture_output=True,
    text=True,
    timeout=900,
    check=False,
    env=os.environ.copy(),   # ← copia TODOS los secretos al subproceso
)
```

**Descripción:**  
El subproceso de entrenamiento del modelo (`python -m app.ml.train_from_db`) hereda el entorno completo del proceso padre, que incluye:

- `DATABASE_URL` (con usuario y contraseña de Supabase)
- `ADMIN_JWT_SECRET`
- `USER_JWT_SECRET`  
- `GOOGLE_CLIENT_SECRET`
- `ADMIN_BOOTSTRAP_SECRET`

En Linux, mientras el subproceso está activo, cualquier proceso del mismo usuario puede leer estos secretos en `/proc/<PID>/environ`. Además, si el subproceso Python falla con una excepción no capturada que incluya variables de entorno en el traceback, los secretos aparecen en `proc.stderr`, que se registra en logs (línea 664: `log.error("train failed: %s", err)`).

**Escenario de explotación:**  
Un atacante con acceso de lectura a los logs del servidor (p.ej. Render Logs, CloudWatch, Papertrail) podría leer secretos si el entrenamiento falla de forma que las variables de entorno aparezcan en la traza del error.

**Remediación:**
```python
import copy
safe_env = copy.copy(os.environ)
for key in ("DATABASE_URL", "ADMIN_JWT_SECRET", "USER_JWT_SECRET",
            "GOOGLE_CLIENT_SECRET", "ADMIN_BOOTSTRAP_SECRET"):
    safe_env.pop(key, None)

proc = subprocess.run(cmd, ..., env=safe_env)
```
El subproceso de entrenamiento puede recibir `DATABASE_URL` como argumento explícito si lo necesita, sin exponer el resto de secretos.

---

### M-03 · Token de acceso Google potencialmente expuesto en logs

**Archivo:** `src/app/api/routes/user_auth.py:242–247`  
**Confianza:** 0.85

**Código vulnerable:**
```python
if token_resp.status_code != 200:
    log.warning(
        "Google token exchange failed: %s %s",
        token_resp.status_code,
        token_resp.text[:500]    # ← cuerpo de respuesta del endpoint de tokens
    )
```

**Descripción:**  
El body de la respuesta de `https://oauth2.googleapis.com/token` se registra en el log cuando falla el intercambio. Aunque en errores estándar de OAuth (invalid_grant, etc.) el cuerpo contiene solo códigos de error, en ciertos escenarios de error parcial o redirección errónea el cuerpo puede contener datos de autenticación. Más importante: si en el futuro se añade logging similar para respuestas exitosas (error frecuente durante debugging), el `access_token` de Google quedaría en logs persistentes.

**Remediación:**
```python
log.warning("Google token exchange failed: status=%s", token_resp.status_code)
# Nunca loguear token_resp.text en ninguna circunstancia
```

---

### M-04 · JWT de administrador sin verificación en base de datos — sin mecanismo de revocación

**Archivo:** `src/app/api/deps_admin.py:38–42`  
**Confianza:** 0.88

**Código vulnerable:**
```python
async def require_admin_token(request, authorization) -> str:
    ...
    return decode_access_token(token, settings.admin_jwt_secret)
    # No hay consulta a admin_users para verificar is_active
```

**Descripción:**  
Al igual que con usuarios (hallazgo A-01), el JWT administrativo se valida únicamente por firma. No se consulta `admin_users` para verificar si el administrador sigue existiendo o sigue activo. El TTL predeterminado es de **240 minutos** (`config.py:71`).

Si las credenciales de un administrador se comprometen y se elimina o desactiva la cuenta, el JWT robado permanece válido durante hasta 4 horas. El único mecanismo de invalidación es rotar `ADMIN_JWT_SECRET` (lo que invalida todas las sesiones de todos los admins).

**Escenario de explotación:**  
Un administrador malintencionado que abandona la organización puede usar su token JWT durante hasta 4 horas después de que su cuenta sea desactivada para ejecutar operaciones sensibles: entrenamiento de modelos, backfill de datos, limpieza de caché, recarga de modelos ML.

**Remediación:**  
Añadir verificación de `is_active` en `require_admin_token`:
```python
from app.db.session import async_session_factory
from app.models.mlb import AdminUser
from sqlalchemy import select

result = await db.execute(select(AdminUser).where(AdminUser.username == username))
admin = result.scalar_one_or_none()
if admin is None or not admin.is_active:
    raise HTTPException(status_code=401, detail="Sesión no válida.")
```

---

### M-05 · Enumeración de emails registrados mediante código de error diferenciado

**Archivo:** `src/app/api/routes/user_auth.py:318–350`  
**Confianza:** 0.93

**Código vulnerable:**
```python
# POST /auth/register
existing = await get_user_by_email(session, body.email)
if existing is not None:
    raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese email.")

# POST /auth/login
if user is None or not user.is_active:
    raise HTTPException(status_code=401, detail="Email o contraseña incorrectos.")
```

**Descripción:**  
El endpoint de registro retorna `HTTP 409` con un mensaje específico para emails ya registrados, mientras que el login retorna `HTTP 401` independientemente de si el email existe o no. Esta diferencia permite a un atacante determinar con certeza qué emails están registrados en la plataforma:

- `POST /auth/register` con email `objetivo@example.com`:
  - `409` → email existe en la base de datos
  - `422` / `400` → email no registrado (falla validación)

No hay rate limiting en este endpoint (véase M-06).

**Remediación:**  
Usar el mismo código de respuesta y mensaje para ambos casos, o añadir un mínimo de 200ms de delay artificial para resistir timing attacks. A largo plazo, implementar verificación de email como requisito previo al registro.

---

### M-06 · Sin rate limiting en endpoints de autenticación de usuario

**Archivo:** `src/app/api/routes/user_auth.py:318–387`  
**Confianza:** 0.97

**Descripción:**  
Los endpoints `POST /auth/login` y `POST /auth/register` no tienen ningún mecanismo de rate limiting, a diferencia del login de admin (`admin.py:273`). Esto permite:

1. **Fuerza bruta ilimitada de contraseñas** contra cualquier cuenta de usuario conocida.
2. **Enumeración masiva de emails** (combinado con M-05).
3. **Creación masiva de cuentas** (account spam/abuse).

El sistema de rate limiting sí existe (`deps_rate_limit.py`) y se usa en otros endpoints (`predict.py:28`, `games.py`), pero no se aplica a las rutas de autenticación de usuario.

**Remediación:**
```python
@router.post("/login", response_model=UserSessionResponse,
             dependencies=[Depends(rate_limit_public_write)])
async def user_login_email(...):

@router.post("/register", response_model=UserSessionResponse,
             dependencies=[Depends(rate_limit_public_write)])
async def user_register(...):
```
Nota: dado que `rate_limit_public_write` también es en memoria (véase M-01), la solución completa requiere un almacén externo compartido.

---

## Hallazgos de Severidad Baja

---

### B-01 · Endpoints de diagnóstico públicos exponen configuración interna

**Archivos:** `src/app/api/routes/admin.py:170–211`, `src/app/api/routes/user_auth.py:134–178`  
**Confianza:** 0.82

**Descripción:**  
`GET /api/v1/admin/auth/ready` y `GET /api/v1/auth/ready` son endpoints **sin autenticación** que revelan:

- Si `ADMIN_JWT_SECRET` / `USER_JWT_SECRET` están configurados.
- Si la tabla `admin_users` / `app_users` existe en la base de datos.
- Mensajes de ayuda que incluyen nombres de scripts de migración y rutas internas:
  ```
  "Ejecuta backend/sql/002_prediction_cache_and_admin.sql"
  "Falta la tabla app_users. Ejecuta backend/sql/007_app_users_and_bets.sql"
  ```

Esta información es valiosa para un atacante que quiera construir un mapa de la arquitectura interna antes de un ataque.

**Remediación:**  
Proteger estos endpoints con autenticación, o devolver únicamente `{"available": true/false}` sin mensajes de diagnóstico en producción.

---

### B-02 · `picture_url` almacenada sin validación de esquema de URL

**Archivo:** `src/app/api/routes/user_auth.py:273–274`  
**Confianza:** 0.80

**Código vulnerable:**
```python
picture = profile.get("picture")
picture_url = str(picture).strip() if isinstance(picture, str) and picture.strip() else None
```

**Descripción:**  
La URL de imagen del perfil de Google se almacena sin validar el esquema (`https://`). Aunque Google normalmente devuelve URLs válidas de sus CDNs, en un escenario de compromiso de TLS o de respuesta manipulada, podría almacenarse una URL con esquema `javascript:`, `data:`, o un servidor controlado por el atacante.

Si el frontend Angular renderiza esta URL en un `<img src>` sin sanitización adicional, no hay riesgo de XSS (Angular escapa automáticamente). Sin embargo, una URL HTTP arbitraria implica tracking externo o carga de contenido de terceros.

**Remediación:**
```python
if picture_url and not picture_url.startswith("https://"):
    picture_url = None
```

---

### B-03 · Ausencia de `.gitignore` propio en `backend/`

**Ruta:** `backend/` (directorio raíz del backend)  
**Confianza:** 0.82

**Descripción:**  
El directorio `backend/` no tiene su propio `.gitignore`. La protección del `.env` depende exclusivamente del `.gitignore` en la raíz del repositorio. Herramientas de IDE (VSCode, JetBrains, etc.) que abren solo la carpeta `backend/` como proyecto raíz no leen el `.gitignore` padre, aumentando el riesgo de commits accidentales de:

- `.env` con credenciales de producción
- `*.joblib` (modelos ML que pueden contener datos de entrenamiento)
- `catboost_info/` (directorio con metadatos de entrenamiento, presente en `backend/`)

**Remediación:**  
Crear `backend/.gitignore` con al menos:
```gitignore
.env
.env.*
!.env.example
*.joblib
catboost_info/
venv/
.venv/
__pycache__/
```

---

## Tabla resumen

| ID   | Título | Severidad | Archivo principal | Confianza |
|------|--------|-----------|-------------------|-----------|
| A-01 | JWT de usuario sin verificación de `is_active` en BD | 🔴 Alta | `deps_user.py:39` | 0.97 |
| A-02 | Reactivación de cuenta via Google OAuth | 🔴 Alta | `services/user_auth.py:34` | 0.95 |
| A-03 | Fuga incondicional de tabla PostgreSQL en errores | 🔴 Alta | `exception_handlers.py:26` | 0.94 |
| M-01 | Rate limiter inefectivo en multi-worker | 🟡 Media | `admin.py:103` | 0.92 |
| M-02 | Secretos expuestos en subproceso de entrenamiento | 🟡 Media | `admin.py:652` | 0.90 |
| M-03 | Token Google en logs de error | 🟡 Media | `user_auth.py:244` | 0.85 |
| M-04 | JWT admin sin revocación en BD | 🟡 Media | `deps_admin.py:41` | 0.88 |
| M-05 | Enumeración de emails por código de respuesta | 🟡 Media | `user_auth.py:329` | 0.93 |
| M-06 | Sin rate limiting en auth de usuario | 🟡 Media | `user_auth.py:353` | 0.97 |
| B-01 | Endpoints de diagnóstico públicos | 🔵 Baja | `admin.py:170` | 0.82 |
| B-02 | `picture_url` sin validación de esquema | 🔵 Baja | `user_auth.py:273` | 0.80 |
| B-03 | Sin `.gitignore` propio en `backend/` | 🔵 Baja | `backend/` | 0.82 |

---

## Plan de remediación priorizado

### Inmediato (sprint actual)
1. **A-02** — Añadir `if not existing.is_active: raise HTTPException(403)` en `upsert_app_user_from_google_profile`. Cambio de 3 líneas, impacto directo en la capacidad de desactivar cuentas.
2. **A-03** — Eliminar la condición `or detail == "database_schema_missing"` de `exception_handlers.py`. Cambio de 1 línea.
3. **M-06** — Añadir `Depends(rate_limit_public_write)` a `/auth/login` y `/auth/register`. Cambio de 2 líneas.
4. **B-03** — Crear `backend/.gitignore`.

### Próximo sprint
5. **A-01** — Añadir verificación de `is_active` en `require_user_id`. Requiere decisión de diseño: consulta DB en cada request vs. reducción del TTL del JWT.
6. **M-04** — Añadir verificación de `is_active` en `require_admin_token`.
7. **M-02** — Limpiar `env` antes de pasar al subproceso de entrenamiento.

### Deuda técnica
8. **M-01** — Migrar rate limiters a Redis compartido.
9. **M-05** — Unificar mensajes de error en registro/login.
10. **M-03** — Eliminar logging del body de respuestas OAuth.
11. **B-01 / B-02** — Ajustes menores de hardening.

---

*Auditoría realizada por análisis estático completo del código fuente. No se ejecutaron pruebas dinámicas (fuzzing, penetration testing activo). Se recomienda complementar con un pentest externo una vez aplicadas las correcciones anteriores.*
