---
name: test-generator
description: >
  Tercera skill del pipeline de testing backend. Genera archivos de pruebas pytest completos
  para FastAPI — cubre endpoints (integration tests con httpx) y servicios (unit tests con mocks
  de repositorio). Opera en dos modos: con plan de pytest-coverage-analyzer o de forma independiente
  por archivo/feature. Usar cuando el usuario quiera escribir tests, crear pruebas para un
  endpoint o servicio específico, generar una nueva feature con cobertura, o continuar el pipeline
  después de test-data-architect. Genera happy paths con loop por campo, errores con
  pytest.mark.parametrize, y cubre todos los caminos de cada función/ruta.
---

# Test Generator

Genera archivos de prueba pytest completos para FastAPI. Cubre endpoints e internos (servicios,
CRUD). Es la **tercera y última skill** del pipeline de testing.

```
[pytest-coverage-analyzer] → [test-data-architect] → [test-generator]
                                                           (esta skill)
```

---

## Stage 0: Determinar Modo de Operación

Al activarse, detectar automáticamente el contexto disponible:

### Modo A — Pipeline completo (viene de las skills anteriores)
Señales: el usuario comparte el reporte de `pytest-coverage-analyzer` o el reporte final
de `test-data-architect`.

→ Leer el plan priorizado: comenzar por archivos 🔴 Inmediata, luego 🟠 Alta, luego 🟡 Media.
→ Los datos de prueba ya están en `tests/mock_data.py` y `tests/conftest.py`.
→ Preguntar: *"¿Generamos todos los archivos del plan o quieres empezar por uno específico?"*

### Modo B — Independiente (feature o archivo específico)
Señales: el usuario pide tests de un archivo/endpoint/feature sin plan previo.

→ Pedir que comparta:
  1. El archivo a probar (`@archivo` o paste)
  2. El schema/DTO que usa (si aplica)
  3. Si existe `tests/mock_data.py` y `tests/conftest.py` — compartirlos para reutilizar datos

→ Si no hay mock_data, avisar: *"No encontré datos de prueba existentes. Puedo generarlos
inline en el test, pero considera correr test-data-architect primero para tener datos
reutilizables. ¿Continuo con datos inline?"*

---

## Stage 1: Leer el Archivo a Probar

Antes de escribir una sola línea de test, leer completamente:

### Para endpoints (`routers/` o `api/`):
- Todas las rutas definidas (GET, POST, PATCH, DELETE, etc.)
- Dependencias inyectadas (`Depends(...)`) — especialmente auth y db
- Schemas de request body y response
- Códigos de status que retorna explícitamente
- Lógica de error que maneja (try/except, raises HTTPException)

### Para servicios (`services/`):
- Todos los métodos públicos
- Parámetros de entrada y tipo de retorno
- Dependencias que inyecta (repositorios, servicios externos)
- Excepciones que lanza (custom exceptions, ValueError, etc.)
- Lógica condicional — cada `if/else` es un camino a probar

### Para CRUD / repositories (`crud/` o `repositories/`):
- Operaciones: create, get, get_multi, update, delete
- Filtros y queries especiales
- Comportamiento cuando no encuentra el registro (None vs raise)

Construir internamente un mapa de cobertura:

```
Archivo: app/services/user_service.py
├── create_user()         → caminos: éxito, email duplicado, error DB
├── get_user()            → caminos: encontrado, no encontrado
├── update_user()         → caminos: éxito por campo, user no existe, sin cambios
├── delete_user()         → caminos: éxito, no existe, intento doble delete
└── get_users_paginated() → caminos: con resultados, vacío, filtros
```

---

## Stage 2: Estructura del Archivo de Test

Cada archivo generado sigue esta estructura:

```python
# tests/test_{nombre_modulo}.py
"""
Tests para {nombre_modulo}.
Generado por test-generator — pipeline de testing backend.

Cobertura:
- Happy path: [lista de funciones/rutas]
- Validaciones: [lista de campos probados]
- Errores: [lista de casos de error]
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient

# Imports del proyecto
from app.main import app
from app.schemas.{schema} import {Schema}Create, {Schema}Update

# Datos de prueba — siempre desde mock_data, nunca inline si existen
from tests.mock_data import (
    {SCHEMA}_VALID,
    {SCHEMA}_MINIMAL,
    {SCHEMA}_NAME_INVALID,
    {SCHEMA}_EMAIL_INVALID,
    # ... todos los que apliquen
)


# ══════════════════════════════════════════════════════════════════════════════
# HAPPY PATH — funcionamiento correcto
# ══════════════════════════════════════════════════════════════════════════════

class Test{Schema}HappyPath:
    """Pruebas de funcionamiento correcto — todos los caminos válidos."""
    ...


# ══════════════════════════════════════════════════════════════════════════════
# VALIDACIONES — errores de campo (422)
# ══════════════════════════════════════════════════════════════════════════════

class Test{Schema}Validations:
    """Pruebas de validación Pydantic — un caso por campo inválido."""
    ...


# ══════════════════════════════════════════════════════════════════════════════
# ERRORES DE NEGOCIO — lógica de error (400, 404, 409, etc.)
# ══════════════════════════════════════════════════════════════════════════════

class Test{Schema}BusinessErrors:
    """Pruebas de errores de negocio — duplicados, no encontrado, permisos, etc."""
    ...
```

---

## Stage 3: Generar Happy Path Tests

### 3a. Create — POST endpoint o método `create_*()`

```python
class TestUserHappyPath:

    async def test_create_user_success(self, client: AsyncClient, auth_headers: dict):
        """Usuario válido completo → 201 + datos correctos en respuesta."""
        response = await client.post(
            "/api/v1/users",
            json=USER_VALID,
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == USER_VALID["name"]
        assert data["email"] == USER_VALID["email"]
        assert "id" in data
        assert "password" not in data  # nunca exponer password en response

    async def test_create_user_minimal_fields(self, client: AsyncClient, auth_headers: dict):
        """Solo campos requeridos → 201. Los opcionales son realmente opcionales."""
        response = await client.post(
            "/api/v1/users",
            json=USER_MINIMAL,
            headers=auth_headers
        )
        assert response.status_code == 201
```

### 3b. Read — GET endpoint o método `get_*()`

```python
    async def test_get_user_by_id(self, client: AsyncClient, auth_headers: dict, created_user_id: str):
        """GET /users/{id} con ID existente → 200 + datos correctos."""
        response = await client.get(
            f"/api/v1/users/{created_user_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["id"] == created_user_id

    async def test_get_users_list(self, client: AsyncClient, auth_headers: dict):
        """GET /users → 200 + lista (puede estar vacía en DB de test)."""
        response = await client.get("/api/v1/users", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
```

### 3c. Update — PATCH endpoint o método `update_*()`

**Estrategia: loop por campo — un request por cada campo actualizable.**
Verifica que cada campo se puede actualizar de forma aislada sin romper los demás.

```python
    @pytest.mark.parametrize("field,new_value", [
        ("name",       "UpdatedName"),
        ("last_name",  "UpdatedLastName"),
        ("birth_date", "1995-06-15"),
        ("phone",      "+52 246 999 0000"),
        # agregar todos los campos del UpdateSchema
    ])
    async def test_update_user_each_field(
        self,
        field: str,
        new_value: str,
        client: AsyncClient,
        auth_headers: dict,
        created_user_id: str
    ):
        """Actualizar cada campo individualmente → 200 + campo actualizado."""
        response = await client.patch(
            f"/api/v1/users/{created_user_id}",
            json={field: new_value},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()[field] == new_value

    async def test_update_user_all_fields(
        self, client: AsyncClient, auth_headers: dict, created_user_id: str
    ):
        """Actualizar todos los campos en un solo request → 200 + todos actualizados."""
        update_payload = {
            "name":       "FullUpdate",
            "last_name":  "AllFields",
            "birth_date": "1990-03-20",
            "phone":      "+52 246 000 1111",
        }
        response = await client.patch(
            f"/api/v1/users/{created_user_id}",
            json=update_payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        for field, value in update_payload.items():
            assert data[field] == value
```

### 3d. Delete — DELETE endpoint o método `delete_*()`

```python
    async def test_delete_user_success(
        self, client: AsyncClient, auth_headers: dict, created_user_id: str
    ):
        """DELETE /users/{id} existente → 204 sin body."""
        response = await client.delete(
            f"/api/v1/users/{created_user_id}",
            headers=auth_headers
        )
        assert response.status_code == 204
```

---

## Stage 4: Generar Validation Tests (errores 422)

**Estrategia: `@pytest.mark.parametrize` — un caso por campo inválido.**
Cada caso es independiente en el reporte de pytest. Si falla `email`, lo ves exactamente.

```python
class TestUserValidations:

    # ── Create validations ──────────────────────────────────────────────────

    @pytest.mark.parametrize("invalid_payload,expected_field", [
        (USER_NAME_INVALID,      "name"),
        (USER_LASTNAME_INVALID,  "last_name"),
        (USER_EMAIL_INVALID,     "email"),
        (USER_AGE_INVALID,       "age"),
        (USER_AGE_TYPE_INVALID,  "age"),
        (USER_ROLE_INVALID,      "role"),
    ])
    async def test_create_user_field_validation(
        self,
        invalid_payload: dict,
        expected_field: str,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Cada campo inválido → 422 con el campo correcto en el detalle del error."""
        response = await client.post(
            "/api/v1/users",
            json=invalid_payload,
            headers=auth_headers
        )
        assert response.status_code == 422
        error_detail = response.json()["detail"]
        # Verificar que el error menciona el campo que esperamos
        error_fields = [err["loc"][-1] for err in error_detail]
        assert expected_field in error_fields, (
            f"Se esperaba error en '{expected_field}' pero los errores fueron: {error_fields}"
        )

    # ── Update validations ──────────────────────────────────────────────────

    @pytest.mark.parametrize("field,invalid_value,expected_field", [
        ("name",  "",         "name"),
        ("email", "bad-mail", "email"),
        ("age",   150,        "age"),
        ("age",   "veinte",   "age"),
        ("role",  "hacker",   "role"),
    ])
    async def test_update_user_field_validation(
        self,
        field: str,
        invalid_value,
        expected_field: str,
        client: AsyncClient,
        auth_headers: dict,
        created_user_id: str
    ):
        """Cada campo inválido en update → 422 con el campo correcto en el error."""
        response = await client.patch(
            f"/api/v1/users/{created_user_id}",
            json={field: invalid_value},
            headers=auth_headers
        )
        assert response.status_code == 422
        error_fields = [err["loc"][-1] for err in response.json()["detail"]]
        assert expected_field in error_fields, (
            f"Se esperaba error en '{expected_field}' pero los errores fueron: {error_fields}"
        )
```

---

## Stage 5: Generar Business Error Tests (400, 404, 409, etc.)

```python
class TestUserBusinessErrors:

    # ── 404 Not Found ───────────────────────────────────────────────────────

    async def test_get_user_not_found(self, client: AsyncClient, auth_headers: dict):
        """GET con ID inexistente → 404."""
        fake_id = "00000000-0000-0000-0000-000000000999"
        response = await client.get(f"/api/v1/users/{fake_id}", headers=auth_headers)
        assert response.status_code == 404

    async def test_update_user_not_found(self, client: AsyncClient, auth_headers: dict):
        """PATCH con ID inexistente → 404."""
        fake_id = "00000000-0000-0000-0000-000000000999"
        response = await client.patch(
            f"/api/v1/users/{fake_id}",
            json={"name": "Ghost"},
            headers=auth_headers
        )
        assert response.status_code == 404

    async def test_delete_user_not_found(self, client: AsyncClient, auth_headers: dict):
        """DELETE con ID inexistente → 404."""
        fake_id = "00000000-0000-0000-0000-000000000999"
        response = await client.delete(f"/api/v1/users/{fake_id}", headers=auth_headers)
        assert response.status_code == 404

    # ── 409 Conflict ────────────────────────────────────────────────────────

    async def test_create_user_duplicate_email(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Crear dos usuarios con el mismo email → segundo intento retorna 409."""
        # Primer usuario — debe crearse exitosamente
        await client.post("/api/v1/users", json=USER_VALID, headers=auth_headers)

        # Segundo intento con el mismo email — debe fallar
        response = await client.post("/api/v1/users", json=USER_VALID, headers=auth_headers)
        assert response.status_code == 409

    async def test_delete_user_twice(
        self, client: AsyncClient, auth_headers: dict, created_user_id: str
    ):
        """Borrar el mismo usuario dos veces → segundo DELETE retorna 404."""
        # Primer delete — exitoso
        first = await client.delete(f"/api/v1/users/{created_user_id}", headers=auth_headers)
        assert first.status_code == 204

        # Segundo delete — el registro ya no existe
        second = await client.delete(f"/api/v1/users/{created_user_id}", headers=auth_headers)
        assert second.status_code == 404

    # ── 401 / 403 Auth ──────────────────────────────────────────────────────

    async def test_create_user_unauthorized(self, client: AsyncClient):
        """Request sin token → 401."""
        response = await client.post("/api/v1/users", json=USER_VALID)
        assert response.status_code == 401

    async def test_create_user_wrong_role(
        self, client: AsyncClient, viewer_auth_headers: dict
    ):
        """Usuario con rol insuficiente → 403."""
        response = await client.post(
            "/api/v1/users",
            json=USER_VALID,
            headers=viewer_auth_headers
        )
        assert response.status_code == 403
```

---

## Stage 6: Unit Tests de Servicios (con mocks de repositorio)

Para los métodos internos de un servicio, mockear el repositorio y probar la lógica pura.

```python
# tests/test_user_service.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.user_service import UserService
from app.schemas.user import UserCreate
from app.core.exceptions import UserNotFoundException, DuplicateEmailException
from tests.mock_data import USER_VALID


class TestUserServiceUnit:
    """Unit tests de UserService — repositorio mockeado."""

    @pytest.fixture
    def mock_repo(self):
        repo = AsyncMock()
        repo.get_by_email = AsyncMock(return_value=None)   # sin duplicado por default
        repo.create = AsyncMock()
        repo.get_by_id = AsyncMock()
        repo.update = AsyncMock()
        repo.delete = AsyncMock()
        return repo

    @pytest.fixture
    def service(self, mock_repo):
        return UserService(repository=mock_repo)

    # ── create_user ─────────────────────────────────────────────────────────

    async def test_create_user_calls_repo(self, service, mock_repo):
        """create_user() llama al repositorio con los datos correctos."""
        payload = UserCreate(**USER_VALID)
        await service.create_user(payload)
        mock_repo.create.assert_called_once()

    async def test_create_user_raises_on_duplicate_email(self, service, mock_repo):
        """Si el email ya existe, create_user() lanza DuplicateEmailException."""
        mock_repo.get_by_email.return_value = MagicMock()  # simula usuario existente
        payload = UserCreate(**USER_VALID)

        with pytest.raises(DuplicateEmailException):
            await service.create_user(payload)

    # ── get_user ────────────────────────────────────────────────────────────

    async def test_get_user_returns_user(self, service, mock_repo):
        """get_user() retorna el usuario cuando existe."""
        mock_user = MagicMock(id="123", name="Josh")
        mock_repo.get_by_id.return_value = mock_user

        result = await service.get_user("123")
        assert result.name == "Josh"

    async def test_get_user_raises_not_found(self, service, mock_repo):
        """get_user() lanza UserNotFoundException cuando el ID no existe."""
        mock_repo.get_by_id.return_value = None

        with pytest.raises(UserNotFoundException):
            await service.get_user("nonexistent-id")

    # ── update_user ─────────────────────────────────────────────────────────

    @pytest.mark.parametrize("field,value", [
        ("name", "NewName"),
        ("last_name", "NewLast"),
        ("birth_date", "1995-01-01"),
    ])
    async def test_update_user_each_field(self, service, mock_repo, field, value):
        """update_user() llama al repositorio con el campo correcto actualizado."""
        mock_repo.get_by_id.return_value = MagicMock()
        mock_repo.update.return_value = MagicMock(**{field: value})

        result = await service.update_user("123", {field: value})
        mock_repo.update.assert_called_once()
        assert getattr(result, field) == value

    # ── delete_user ─────────────────────────────────────────────────────────

    async def test_delete_user_success(self, service, mock_repo):
        """delete_user() llama a repo.delete() cuando el usuario existe."""
        mock_repo.get_by_id.return_value = MagicMock()
        await service.delete_user("123")
        mock_repo.delete.assert_called_once_with("123")

    async def test_delete_user_raises_not_found(self, service, mock_repo):
        """delete_user() lanza UserNotFoundException si el ID no existe."""
        mock_repo.get_by_id.return_value = None

        with pytest.raises(UserNotFoundException):
            await service.delete_user("nonexistent-id")
```

---

## Stage 7: Fixture de Recurso Creado (helper para tests de update/delete)

Agregar en `conftest.py` una fixture que crea el recurso y retorna su ID,
para que los tests de update/delete no dependan del orden de ejecución:

```python
# Agregar en tests/conftest.py

@pytest.fixture
async def created_user_id(client: AsyncClient, auth_headers: dict) -> str:
    """Crea un usuario de prueba y retorna su ID. Se limpia automáticamente."""
    response = await client.post(
        "/api/v1/users",
        json=USER_VALID,
        headers=auth_headers
    )
    assert response.status_code == 201
    user_id = response.json()["id"]
    yield user_id
    # Cleanup — borrar el usuario al terminar el test
    await client.delete(f"/api/v1/users/{user_id}", headers=auth_headers)
```

---

## Stage 8: Resumen de Cobertura Generada

Al terminar cada archivo, reportar:

```
## 📝 Tests Generados — app/services/user_service.py

Archivo: tests/test_user_service.py

### Cobertura por función
| Función | Happy Path | Validaciones | Errores | Total tests |
|---------|-----------|--------------|---------|-------------|
| create_user() | ✅ 2 tests | ✅ 6 params | ✅ 2 tests | 10 |
| get_user() | ✅ 1 test | — | ✅ 1 test | 2 |
| update_user() | ✅ 4 params + 1 full | ✅ 5 params | ✅ 1 test | 11 |
| delete_user() | ✅ 1 test | — | ✅ 2 tests | 3 |
| get_users_paginated() | ✅ 2 tests | — | — | 2 |

**Total: 28 tests generados**
**Cobertura estimada: ~85%** (líneas no cubiertas: manejo de timeout de DB)

---
¿Continuamos con el siguiente archivo del plan o hay algo que ajustar en estos tests?
```

---

## Reglas globales de esta skill

- **Nunca usar datos inline** si existe `mock_data.py` — siempre importar desde ahí.
- **Cada test tiene una sola razón para fallar** — no mezclar asserts de campos distintos
  en el mismo test salvo en el caso de `test_update_all_fields`.
- **parametrize para errores, loop interno para happy path de update** — ver Stage 3c y 4.
- **Fixtures para recursos creados** — nunca hardcodear IDs, siempre crear el recurso
  en el test o en una fixture de conftest.
- **Cleanup explícito** — toda fixture que crea datos en DB debe limpiarlos en el `yield`.
- **Nombres descriptivos**: `test_create_user_duplicate_email` no `test_create_error_2`.
- **El mensaje de assert explica el fallo**: siempre incluir el string en el tercer
  argumento de `assert` cuando no es obvio, especialmente en parametrize.
- Consultar `references/pytest-patterns.md` para patterns avanzados de fixtures,
  mocking de servicios externos y tests de paginación.
