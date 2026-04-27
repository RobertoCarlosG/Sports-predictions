# Procedimientos de prueba de seguridad — Sports Predictions

Pruebas reproducibles para validar hallazgos y regresiones **después** de cambios. Sustituir `$API` por la base URL del backend (ej. `https://…onrender.com` o `http://127.0.0.1:8000`).

**Advertencia:** No ejecutar bucles de fuerza bruta contra producción sin autorización; usar staging o local.

---

## 1. Autenticación admin (Bloque A)

### 1.1 Login — mensaje genérico

```bash
curl -sS -o /dev/null -w "%{http_code}\n" \
  -H 'Content-Type: application/json' \
  -d '{"username":"noexiste","password":"x"}' \
  "$API/api/v1/admin/auth/login"

curl -sS -o /dev/null -w "%{http_code}\n" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"mal"}' \
  "$API/api/v1/admin/auth/login"
```

**Esperado actual:** ambos `401`. Tras rate limit (si se implementa): `429` tras N intentos.

### 1.2 Atributos de cookie (tras login válido)

```bash
curl -sS -i -c /tmp/sp_cookies.txt \
  -H 'Content-Type: application/json' \
  -d '{"username":"TU_USER","password":"TU_PASS"}' \
  "$API/api/v1/admin/auth/login" | grep -i set-cookie
```

**Verificar:** `HttpOnly`, `Secure` (si HTTPS), `SameSite=None` o `Lax`, `Path=/`, `Max-Age` acorde a TTL.

### 1.3 Sesión sin JWT en body

Inspeccionar cuerpo JSON de login: debe incluir `username`, TTL hints; **no** debe aparecer el token JWT en claro.

### 1.4 Bootstrap desactivado

Con `ADMIN_BOOTSTRAP_SECRET` vacío en servidor:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" \
  -H 'Content-Type: application/json' \
  -H 'X-Admin-Bootstrap-Secret: cualquiera' \
  -d '{"username":"x","password":"y"}' \
  "$API/api/v1/admin/auth/bootstrap"
```

**Esperado:** `404`.

---

## 2. CSRF (Bloque B) — prueba conceptual

### 2.1 PoC HTML (solo en entorno de prueba)

Con sesión iniciada en el navegador como operador, abrir un archivo HTML servido desde **otro origen** (ej. `http://evil.local`) que haga:

```html
<form action="$API/api/v1/admin/auth/logout" method="POST" id="f"></form>
<script>document.getElementById('f').submit();</script>
```

Si la cookie se envía y el servidor procesa el POST sin token CSRF, el hallazgo se confirma.

**Mitigación esperada post-fix:** rechazo por falta de header CSRF o token inválido.

---

## 3. Endpoints públicos (Bloque C)

### 3.1 Coste sync

```bash
time curl -sS "$API/api/v1/games?date=2025-04-01&sync=true&fetch_details=true&include_predictions=true" -o /dev/null
```

Repetir en paralelo (bash `&`) para evaluar carga local/staging.

### 3.2 Límite sync-range

```bash
curl -sS -o /dev/null -w "%{http_code}\n" \
  -H 'Content-Type: application/json' \
  -d '{"start_date":"2025-01-01","end_date":"2025-12-31","fetch_details":true}' \
  "$API/api/v1/mlb/sync-range"
```

**Esperado:** `400` si el rango excede el máximo permitido por request.

---

## 4. Fuga de información (Bloque G)

### 4.1 Errores con DEBUG

Con `DEBUG=true`, provocar error de BD (ej. tabla inexistente en entorno de prueba) y comprobar si el JSON incluye `"technical"`.

```bash
# Tras configurar DEBUG según entorno
curl -sS "$API/api/v1/games?date=2020-01-01&sync=true" | jq .
```

**Producción esperada:** sin `technical` en respuestas al cliente.

### 4.2 Auth ready

```bash
curl -sS "$API/api/v1/admin/auth/ready" | jq .
```

Documentar qué campos son aceptables exponer en prod.

---

## 5. Cabeceras (Bloque E)

```bash
curl -sSI "$API/health"
curl -sSI "$API/"
curl -sSI "https://TU-DOMINIO-VERCEL.vercel.app/"
```

Comprobar presencia de HSTS (si aplica), `X-Content-Type-Options`, etc.

---

## 6. Dependencias

```bash
cd Sports-Predictions/frontend && npm audit --omit=dev
cd Sports-Predictions/backend && pip-audit --cache-dir .pip-audit-cache -l
```

---

## 7. Checklist rápido pre-release

- [ ] `DEBUG=false` en Render (o equivalente).
- [ ] `CORS_ORIGINS` solo orígenes reales de prod.
- [ ] Secretos rotados tras cualquier filtración.
- [ ] `npm audit` sin highs sin ticket vinculado.
- [ ] Panel admin con mitigación CSRF desplegada.
- [ ] Rate limit login activo en prod.
