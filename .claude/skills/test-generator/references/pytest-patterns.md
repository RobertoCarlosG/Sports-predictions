# Pytest Patterns — Referencia Avanzada

## Fixtures de scope

```python
# scope="function" (default) — se ejecuta por cada test
@pytest.fixture
async def created_user(client, auth_headers):
    ...

# scope="module" — se ejecuta una vez por archivo de test
# Útil para datos de solo lectura que no se modifican
@pytest.fixture(scope="module")
async def readonly_user(client, auth_headers):
    ...

# scope="session" — se ejecuta una vez en toda la sesión de pytest
# Solo para setup de infraestructura (DB, cliente base)
@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    ...
```

**Regla**: Usar el scope más corto posible. Los tests deben ser independientes.
Si un test falla por el estado que dejó otro, el scope es demasiado amplio.

---

## Mocking de servicios externos

### Mockear un servicio en un endpoint (patch en el path correcto)

```python
# El path debe ser donde SE USA, no donde está definido
@patch("app.api.v1.endpoints.users.email_service.send_welcome_email")
async def test_create_user_sends_email(mock_send, client, auth_headers):
    mock_send = AsyncMock(return_value=None)
    response = await client.post("/api/v1/users", json=USER_VALID, headers=auth_headers)
    assert response.status_code == 201
    mock_send.assert_called_once()
```

### Mockear con pytest-mock (más limpio que @patch)

```python
async def test_create_user_sends_email(client, auth_headers, mocker):
    mock_send = mocker.patch(
        "app.api.v1.endpoints.users.email_service.send_welcome_email",
        new_callable=AsyncMock
    )
    response = await client.post("/api/v1/users", json=USER_VALID, headers=auth_headers)
    assert mock_send.called
```

### Simular fallo de servicio externo

```python
async def test_create_user_email_failure_still_creates(client, auth_headers, mocker):
    """Si el email falla, el usuario igual se crea (dependiendo del diseño)."""
    mocker.patch(
        "app.services.email_service.send_welcome_email",
        side_effect=Exception("SMTP timeout")
    )
    response = await client.post("/api/v1/users", json=USER_VALID, headers=auth_headers)
    # Ajustar según comportamiento esperado del sistema
    assert response.status_code in (201, 500)
```

---

## Tests de paginación

```python
@pytest.mark.parametrize("skip,limit,expected_count", [
    (0, 10, 3),   # primera página, hay 3 registros en total
    (0, 2,  2),   # primera página con límite 2
    (2, 10, 1),   # segunda página, solo queda 1
    (5, 10, 0),   # skip mayor que total → lista vacía
])
async def test_get_users_pagination(skip, limit, expected_count, client, auth_headers, three_users):
    response = await client.get(
        f"/api/v1/users?skip={skip}&limit={limit}",
        headers=auth_headers
    )
    assert response.status_code == 200
    assert len(response.json()) == expected_count


@pytest.fixture
async def three_users(client, auth_headers):
    """Crea 3 usuarios de prueba para tests de paginación."""
    ids = []
    for i in range(3):
        payload = {**USER_VALID, "email": f"user{i}@example.com"}
        r = await client.post("/api/v1/users", json=payload, headers=auth_headers)
        ids.append(r.json()["id"])
    yield
    for uid in ids:
        await client.delete(f"/api/v1/users/{uid}", headers=auth_headers)
```

---

## Tests de filtros y búsqueda

```python
async def test_filter_users_by_role(client, auth_headers, two_users_different_roles):
    response = await client.get("/api/v1/users?role=admin", headers=auth_headers)
    assert response.status_code == 200
    results = response.json()
    assert all(u["role"] == "admin" for u in results)

async def test_search_users_by_name(client, auth_headers, created_user_id):
    response = await client.get("/api/v1/users?search=Josh", headers=auth_headers)
    assert response.status_code == 200
    assert any(u["name"] == "Josh" for u in response.json())
```

---

## Verificar estructura del response (no solo status code)

```python
async def test_create_user_response_shape(client, auth_headers):
    """Verificar que el response tiene la estructura esperada."""
    response = await client.post("/api/v1/users", json=USER_VALID, headers=auth_headers)
    data = response.json()

    # Campos que deben estar presentes
    required_fields = {"id", "name", "last_name", "email", "role", "created_at"}
    assert required_fields.issubset(data.keys()), (
        f"Faltan campos en el response: {required_fields - data.keys()}"
    )

    # Campos que NUNCA deben exponerse
    forbidden_fields = {"password", "hashed_password", "salt"}
    assert not forbidden_fields.intersection(data.keys()), (
        f"Campos sensibles expuestos: {forbidden_fields.intersection(data.keys())}"
    )

    # Tipos de datos
    assert isinstance(data["id"], str)
    assert isinstance(data["created_at"], str)  # ISO format
```

---

## Patrones para tests de autenticación

### Tabla de roles y permisos

```python
@pytest.mark.parametrize("role,endpoint,method,expected_status", [
    ("admin",   "/api/v1/users",      "POST",   201),
    ("user",    "/api/v1/users",      "POST",   403),
    ("viewer",  "/api/v1/users",      "POST",   403),
    ("admin",   "/api/v1/users/123",  "DELETE", 204),
    ("user",    "/api/v1/users/123",  "DELETE", 403),
])
async def test_role_permissions(role, endpoint, method, expected_status, client, get_token_for_role):
    headers = {"Authorization": f"Bearer {get_token_for_role(role)}"}
    response = await getattr(client, method.lower())(endpoint, headers=headers)
    assert response.status_code == expected_status
```

### Token expirado

```python
async def test_expired_token_returns_401(client):
    expired_headers = {"Authorization": "Bearer expired.token.here"}
    response = await client.get("/api/v1/users", headers=expired_headers)
    assert response.status_code == 401
    assert "expired" in response.json().get("detail", "").lower()
```

---

## Tests de concurrencia (casos borde avanzados)

```python
import asyncio

async def test_concurrent_create_same_email(client, auth_headers):
    """Dos requests simultáneos con el mismo email → solo uno debe crearse."""
    tasks = [
        client.post("/api/v1/users", json=USER_VALID, headers=auth_headers),
        client.post("/api/v1/users", json=USER_VALID, headers=auth_headers),
    ]
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    status_codes = [r.status_code for r in responses if hasattr(r, "status_code")]

    # Uno debe ser 201, el otro 409
    assert 201 in status_codes
    assert 409 in status_codes
```

---

## Convenciones de nombres de tests

```
test_{recurso}_{acción}_{condición}

Ejemplos:
test_create_user_success
test_create_user_duplicate_email
test_create_user_invalid_name
test_get_user_not_found
test_update_user_each_field          ← parametrize de happy path
test_update_user_field_validation    ← parametrize de errores
test_delete_user_twice               ← error de negocio
test_get_users_pagination            ← parametrize de paginación
```

**Anti-patrones a evitar:**
```
test_user_1          ← ¿qué prueba?
test_error_case      ← ¿qué error?
test_api             ← demasiado genérico
test_create_and_update_and_delete  ← demasiados comportamientos en uno
```

---

## Orden recomendado de generación de tests por archivo

1. Happy path CREATE
2. Happy path READ (get by id + list)
3. Happy path UPDATE (parametrize por campo + all fields)
4. Happy path DELETE
5. Validaciones CREATE (parametrize por campo inválido)
6. Validaciones UPDATE (parametrize por campo inválido)
7. Error 404 (get, update, delete con ID inexistente)
8. Error 409 (duplicados)
9. Error 401/403 (sin auth, rol incorrecto)
10. Casos borde específicos del dominio (doble delete, paginación, filtros)
