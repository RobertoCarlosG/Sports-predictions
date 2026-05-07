# Base de datos: Supabase free tier y pooler transaccional

> Contexto del monorepo y despliegue: [deploy.md](deploy.md) · [estatus-actual.md](estatus-actual.md).

## Free tier: conexión directa sin IPv4

En el dashboard de Supabase suele aparecer:

> **Not IPv4 compatible** — Use Session Pooler if on an IPv4 network or purchase IPv4 add-on

Es decir: la URL de **conexión directa** al Postgres (`db.<ref>.supabase.co`, puerto **5432**) **no ofrece IPv4** en el plan gratuito. Redes que solo tienen salida IPv4 (muy habitual en **Render**, Fly, etc.) no pueden alcanzar ese endpoint de forma fiable; a veces el síntoma es `OSError: [Errno 101] Network is unreachable` al conectar.

**No es un bug de esta API**: es una limitación de red / plan.

## Configuración recomendada para este proyecto (por ahora)

Usar el **Transaction pooler** de Supabase (PgBouncer en modo transacción):

- Host tipo `aws-0-…pooler.supabase.com` o el que indique el dashboard.
- Puerto típico **6543** (pooler), no 5432 (directo).
- Copia la cadena **“Transaction pool”** / “Connection pooling” en modo **Transaction** desde Supabase.

El backend está alineado con **PgBouncer en modo transacción**:

- `NullPool` (el pool real lo hace Supabase).
- `prepared_statement_cache_size=0` en la URL del motor.
- `statement_cache_size=0` y nombres únicos de prepared statement en asyncpg.

Así se evitan errores de tipo `prepared statement "__asyncpg_stmt_*" does not exist` que aparecen al reutilizar conexiones detrás del pooler.

## Qué no usar en free tier (sin add-on IPv4)

- **`DATABASE_URL` de conexión directa** (5432) desde Render si tu red es IPv4-only: fallará o será intermitente.
- **`DATABASE_FORCE_IPV4=true`**: solo tiene sentido si el host **tiene** registro A / IPv4 (p. ej. **IPv4 add-on** de pago o entorno donde el directo sea IPv4). En free tier **sin** IPv4 en directo, **no soluciona** el problema; usa pooler.

## Alternativas si más adelante quieres optimizar

| Opción | Notas |
|--------|--------|
| **Transaction pooler** (actual) | Compatible con este repo tal cual. |
| **Session pooler** | Mejor si quieres quitar `NullPool` y usar pool en la app; requiere probar y ajustar `session.py`. |
| **IPv4 add-on** (pago) | Permite conexión directa con IPv4; entonces puedes valorar URL directa y, si hace falta, `DATABASE_FORCE_IPV4`. |

## Resumen

1. En **Supabase → Connect → Connection pooling**, elige **Transaction** y pega esa URL en `DATABASE_URL` en Render (con `postgresql+asyncpg://` o `postgres://`; el backend normaliza el driver).
2. No dependas de **conexión directa** en free tier sin IPv4 si despliegas en IPv4-only.
3. El código del pooler + asyncpg está pensado para este escenario **por defecto**.
