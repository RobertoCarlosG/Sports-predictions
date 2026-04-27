# Backlog de seguridad — Sports Predictions

Tickets derivados del [SECURITY-AUDIT-REPORT.md](./SECURITY-AUDIT-REPORT.md). Prioridad: **P0** crítico inmediato, **P1** alto, **P2** medio, **P3** bajo.

| ID | Prioridad | Título | Owner sugerido | Bloque |
|----|-----------|--------|----------------|--------|
| SEC-001 | P0 | Rotar credenciales Supabase/Postgres si `.env` estuvo expuesto; confirmar secretos solo en gestor (Render/Supabase), nunca en repo | DevOps | D |
| SEC-002 | P0 | Forzar `DEBUG=false` en producción (Render); verificar env | Backend | D, G |
| SEC-003 | P0 | Mitigar CSRF en rutas admin con cookie: token synchronizer (header `X-CSRF-Token`) + cookie doble, o validar `Origin`/`Referer` contra allowlist, o SameSite strict si front y API comparten sitio | Backend + Frontend | B |
| SEC-004 | P1 | Rate limiting en `POST /admin/auth/login` (por IP + opcional por username); respuesta 429 uniforme | Backend | A |
| SEC-005 | P1 | Whitelist de ruta para `TrainModelBody.output` (solo bajo `backend/src/app/ml/artifacts/` o similar); rechazar `..` y paths absolutos | Backend | F |
| SEC-006 | P1 | Rate limiting o API key / auth en endpoints públicos costosos (`games?sync=true`, `mlb/sync-range`, `predict/refresh`, `games/.../weather`) | Backend | C |
| SEC-007 | P1 | Sustituir o aislar `xlsx` (SheetJS): evaluar `exceljs`, export CSV, o versión parcheada; CVE high sin fix upstream | Frontend | K |
| SEC-008 | P2 | Añadir cabeceras de seguridad en FastAPI (middleware) y `vercel.json` (`headers`) para SPA | Backend + Frontend | E |
| SEC-009 | P2 | Endurecer CORS en prod: eliminar localhost de `CORS_ORIGINS` del entorno productivo | Backend | D |
| SEC-010 | P2 | JWT: añadir `iss`, `aud`, `jti`; considerar lista de revocación o rotación corta; documentar impacto al cambiar `ADMIN_JWT_SECRET` | Backend | A, L |
| SEC-011 | P2 | `hmac.compare_digest` para `X-Admin-Bootstrap-Secret` y secretos comparados en constante tiempo | Backend | A |
| SEC-012 | P2 | Política de contraseña admin (longitud mínima 12–14, complejidad opcional) en Pydantic + mensajes claros | Backend | A |
| SEC-013 | P2 | Guard de ruta Angular `CanActivate` en `/operations` que llame `adminApi.checkSession()` y redirija o muestre solo login | Frontend | H |
| SEC-014 | P2 | Auditoría append-only: tabla `admin_audit_log` o logs estructurados (JSON) con usuario, ruta, timestamp, request-id | Backend | J |
| SEC-015 | P2 | Dockerfile: usuario no root, `read_only` root fs si es viable | DevOps | L |
| SEC-016 | P2 | Revisar RLS en Supabase para tablas sensibles o documentar que solo la API accede con rol único y sin Studio público | DBA / DevOps | I |
| SEC-017 | P3 | Introducir lockfile Python (`uv.lock` / `requirements.lock`) y CI `pip-audit` | Backend | K |
| SEC-018 | P3 | Alembic o versionado estricto de migraciones SQL | Backend | I |
| SEC-019 | P3 | Reducir información en `GET /admin/auth/ready` en entornos prod (o cachear sin detalles) | Backend | G |
| SEC-020 | P3 | Documentar runbook: rotación JWT, incidente de cookie robada, restore BD | DevOps | L |

## Orden sugerido de implementación

1. SEC-001, SEC-002, SEC-003  
2. SEC-004, SEC-005, SEC-006  
3. SEC-007, SEC-008, SEC-009  
4. Resto por capacidad del equipo.

## Definición de hecho (seguridad)

- No hay secretos en artefactos de CI ni en imágenes Docker innecesarias.
- `npm audit` / `pip-audit` en CI sin critical/high sin excepción documentada.
- Panel admin resistente a CSRF en el modelo de amenaza cross-site actual.
- Producción sin `DEBUG` y sin campo `technical` en respuestas al cliente.
