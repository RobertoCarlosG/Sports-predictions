---
name: test-data-architect
description: >
  Segunda skill del pipeline de testing backend. Recibe el plan de pruebas de pytest-coverage-analyzer
  (o una descripción de los archivos/módulos a probar) y prepara todos los datos de prueba necesarios
  antes de escribir los tests. Busca si existe un archivo mock_data / test_data / conftest.py con
  fixtures, y si no, los crea. Genera objetos válidos completos + objetos inválidos por campo para
  probar validaciones Pydantic y mensajes de error específicos. Usar cuando el usuario quiera preparar
  datos de prueba, crear fixtures, generar objetos de test con constraints, o verificar que las
  validaciones de campos retornan los errores correctos. Es la extensión natural de pytest-coverage-analyzer
  y el paso previo a test-generator.
---

# Test Data Architect

Prepara todos los datos de prueba necesarios para el pipeline de testing FastAPI/Pydantic.
Genera objetos válidos + inválidos por campo con sus constraints, evitando `MagicMock` en favor
de datos reales y representativos.

```
[pytest-coverage-analyzer] → [test-data-architect] → [test-generator]
                                    (esta skill)
```

---

## Stage 1: Recibir el Contexto

Esta skill puede activarse de dos formas:

### Forma A — Viene del plan de pytest-coverage-analyzer
El usuario comparte el output de la skill anterior. Extraer:
- Lista de archivos prioritarios
- Schemas relacionados por archivo
- Modelos SQLAlchemy relacionados
- Dependencias a mockear

### Forma B — Invocación directa
El usuario pide preparar datos para un módulo específico. Pedir:
- ¿Qué schema(s) o modelo(s) necesitas cubrir?
- ¿Tienes el archivo del schema para compartirlo? (vía `@` o paste)

En cualquier caso, **siempre pedir los archivos de schema** antes de generar datos.
No inventar campos — leerlos directamente del código Pydantic.

---

## Stage 2: Buscar Archivos de Mock Data Existentes

Antes de crear nada, buscar si ya existen archivos de datos de prueba:

### Paths donde buscar (en orden):
```
tests/
├── mock_data.py
├── test_data.py
├── fixtures.py
├── conftest.py          ← más común en proyectos pytest
├── factories.py
└── data/
    ├── mock_data.py
    └── users.json
```

Pedir al usuario: *"¿Puedes compartir el contenido de `tests/conftest.py` y cualquier
archivo `mock_data.py` o `test_data.py` que tengas? Si no existe ninguno, lo creamos desde cero."*

### Si existe conftest.py:
- Leer las fixtures existentes
- Identificar qué entidades ya tienen datos de prueba
- **No duplicar** — solo agregar lo que falta
- Anotar si usan `MagicMock` → sugerir reemplazar con datos reales

### Si NO existe ningún archivo:
- Crear `tests/conftest.py` desde cero
- Crear `tests/mock_data.py` para los diccionarios de datos
- Ver Stage 4 para la estructura

---

## Stage 3: Analizar los Schemas Pydantic

Para cada schema compartido, extraer:

```python
# Ejemplo de schema a analizar
class UserCreate(BaseModel):
    name: str
    last_name: str
    email: EmailStr
    age: int = Field(gt=0, lt=120)
    role: Literal["admin", "user", "viewer"] = "user"
    phone: Optional[str] = None
```

Extraer por campo:
- **Nombre del campo**
- **Tipo** (str, int, EmailStr, UUID, etc.)
- **¿Requerido?** (sin default = requerido)
- **Validators / constraints**: `gt`, `lt`, `ge`, `le`, `min_length`, `max_length`, `regex`, `Literal`
- **¿Opcional?** (`Optional[X]` o con `None` como default)

Construir una tabla interna:

| Campo | Tipo | Requerido | Constraints | Puede ser None |
|-------|------|-----------|-------------|----------------|
| name | str | ✅ | — | ❌ |
| last_name | str | ✅ | — | ❌ |
| email | EmailStr | ✅ | formato email | ❌ |
| age | int | ✅ | > 0, < 120 | ❌ |
| role | Literal | ❌ | ["admin","user","viewer"] | ❌ |
| phone | str | ❌ | — | ✅ |

---

## Stage 4: Generar Datos de Prueba

### 4a. Objeto válido completo

Un objeto que pasa todas las validaciones. Usar datos realistas, no `"string"` o `123`.

```python
# mock_data.py

USER_VALID = {
    "name": "Josh",
    "last_name": "Dahmer",
    "email": "josh.dahmer@example.com",
    "age": 28,
    "role": "user",
    "phone": "+52 246 100 0000"
}
```

**Reglas para datos válidos:**
- Strings: nombres reales, emails reales (dominio `@example.com`)
- Ints: valores en el rango medio del constraint (si `gt=0, lt=120` → usar `28`, no `1` ni `119`)
- Enums/Literal: usar el valor default o el primero de la lista
- UUIDs: generar uno fijo con `uuid.UUID("00000000-0000-0000-0000-000000000001")`
- Fechas: usar `datetime(2024, 1, 15, 10, 30, 0)` — fechas fijas, no `datetime.now()`
- Opcionales: **incluirlos** en el objeto válido con un valor real

### 4b. Objetos inválidos por campo

**Un objeto inválido separado por cada campo requerido** que viola exactamente una constraint.
El resto de los campos deben ser válidos.

Formato del nombre: `{SCHEMA}_{CAMPO}_INVALID`

```python
# mock_data.py — continuación

# name vacío → debe retornar error en campo "name"
USER_NAME_INVALID = {**USER_VALID, "name": ""}

# email malformado → debe retornar error en campo "email"
USER_EMAIL_INVALID = {**USER_VALID, "email": "not-an-email"}

# age fuera de rango → debe retornar error en campo "age"
USER_AGE_INVALID = {**USER_VALID, "age": 150}

# age tipo incorrecto → debe retornar error en campo "age"
USER_AGE_TYPE_INVALID = {**USER_VALID, "age": "twenty"}

# role valor no permitido → debe retornar error en campo "role"
USER_ROLE_INVALID = {**USER_VALID, "role": "superadmin"}
```

### 4c. Objeto mínimo válido (solo campos requeridos)

```python
# Solo los campos obligatorios — para probar que los opcionales son realmente opcionales
USER_MINIMAL = {
    "name": "Josh",
    "last_name": "Dahmer",
    "email": "josh.dahmer@example.com",
    "age": 28
    # role tiene default, phone es opcional — ambos omitidos intencionalmente
}
```

### 4d. Tipos de invalidación por tipo de campo

| Tipo de campo | Casos inválidos a generar |
|--------------|--------------------------|
| `str` requerido | `""` (vacío), `None` |
| `str` con `min_length=N` | string de N-1 caracteres |
| `str` con `max_length=N` | string de N+1 caracteres |
| `EmailStr` | `"notanemail"`, `"@nodomain"` |
| `int` con `gt=X` | `X` (igual al límite, no mayor) |
| `int` con `lt=X` | `X` (igual al límite, no menor) |
| `Literal[a,b,c]` | `"valor_no_en_lista"` |
| `UUID` | `"not-a-uuid"`, `"123"` |
| `bool` | `"true"` (string, no bool) |
| `Optional[str]` | No generar caso inválido — es opcional |

---

## Stage 5: Generar conftest.py con Fixtures

Después de definir los datos en `mock_data.py`, crear fixtures en `conftest.py`:

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.base import Base
from app.core.config import settings
from tests.mock_data import USER_VALID, USER_MINIMAL

# ── Base de datos de prueba ──────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine_test = create_async_engine(TEST_DATABASE_URL, echo=False)
AsyncTestSession = sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)

@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def db_session():
    async with AsyncTestSession() as session:
        yield session
        await session.rollback()

# ── Cliente HTTP de prueba ───────────────────────────────────────────────────

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

# ── Fixtures de datos ────────────────────────────────────────────────────────

@pytest.fixture
def valid_user_data():
    """Datos de usuario completos y válidos."""
    return USER_VALID.copy()

@pytest.fixture
def minimal_user_data():
    """Solo campos requeridos — verifica que opcionales son realmente opcionales."""
    return USER_MINIMAL.copy()

# ── Fixture de usuario autenticado (si aplica) ───────────────────────────────

@pytest.fixture
async def auth_headers(client):
    """Obtiene token de autenticación para pruebas de endpoints protegidos."""
    response = await client.post("/api/v1/auth/login", json={
        "email": USER_VALID["email"],
        "password": "TestPassword123!"   # ajustar al campo correcto
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

---

## Stage 6: Checklist de Cobertura de Datos

Antes de generar el reporte final, cruzar el **plan de pytest-coverage-analyzer** contra
los objetos existentes en `mock_data.py` para producir un diff real: qué está listo y qué falta.

### Cómo hacer el cruce

Para cada archivo del plan de prioridad (Inmediata → Alta → Media):

1. Identificar el schema principal que usa ese archivo
   - Services → buscar `{SCHEMA}Create`, `{SCHEMA}Update`, `{SCHEMA}Response`
   - Endpoints → buscar los schemas del request body y response
   - CRUD → buscar el modelo SQLAlchemy + schema asociado

2. Buscar en `mock_data.py` si existen estos objetos:
   - `{SCHEMA}_VALID` → happy path
   - `{SCHEMA}_MINIMAL` → solo campos requeridos
   - Al menos un `{SCHEMA}_{CAMPO}_INVALID` → validaciones

3. Marcar el estado:
   - ✅ **Listo** — existe `_VALID` + al menos un `_INVALID`
   - 🟡 **Parcial** — existe `_VALID` pero faltan los `_INVALID`
   - 🔲 **Pendiente** — no existe ningún objeto para este schema
   - ➖ **No aplica** — el archivo no usa schemas propios (ej. utils puros)

### Reporte del checklist

```
## ✅ Checklist de Datos de Prueba vs Plan de Coverage

| Archivo (del plan) | Schema | _VALID | _MINIMAL | _INVALID | Estado |
|--------------------|--------|--------|----------|----------|--------|
| app/services/user_service.py | UserCreate | ✅ | ✅ | ✅ x4 | ✅ Listo |
| app/api/v1/endpoints/payments.py | PaymentCreate | ✅ | ❌ | ❌ | 🟡 Parcial |
| app/services/order_service.py | OrderCreate | ❌ | ❌ | ❌ | 🔲 Pendiente |
| app/utils/date_helpers.py | — | — | — | — | ➖ No aplica |

---
Resumen:
- ✅ Listos para testing: N archivos
- 🟡 Parciales (faltan inválidos): N archivos → se generan ahora
- 🔲 Sin datos: N archivos → se generan ahora
```

Después del checklist, generar automáticamente los datos que faltan (Parciales y Pendientes)
siguiendo el Stage 4. No preguntar — completar el gap y reportar qué se creó.

---

## Stage 7: Reporte Final

```
## 🗂️ Reporte de Datos de Prueba

### Archivos generados / actualizados
- `tests/mock_data.py` — [N] objetos nuevos agregados ([M] ya existían)
- `tests/conftest.py`  — [N] fixtures nuevas agregadas ([M] ya existían)

---

### Por schema

#### UserCreate
| Objeto | Propósito | Campo inválido |
|--------|-----------|----------------|
| USER_VALID | Happy path completo | — |
| USER_MINIMAL | Solo campos requeridos | — |
| USER_NAME_INVALID | Verifica error en "name" | name = "" |
| USER_EMAIL_INVALID | Verifica error en "email" | email malformado |
| USER_AGE_INVALID | Verifica error en "age" | age = 150 (> 120) |
| USER_ROLE_INVALID | Verifica error en "role" | role no en Literal |

#### PaymentCreate ← nuevo, generado en esta sesión
| Objeto | Propósito | Campo inválido |
|--------|-----------|----------------|
| PAYMENT_VALID | Happy path completo | — |
| PAYMENT_MINIMAL | Solo campos requeridos | — |
| PAYMENT_AMOUNT_INVALID | Verifica error en "amount" | amount = "-10.00" |
| ...   | ...       | ...            |

---

### Dependencias identificadas para mockear en los tests

(Los mocks de servicios externos van en el archivo de test, NO en mock_data.py)
- `app/core/email.py` → `AsyncMock` para `send_welcome_email`
- `app/integrations/stripe.py` → `AsyncMock` para `create_payment`

---

### ⚠️ Campos sin datos inválidos (opcionales)
- `phone` en UserCreate — Optional[str], no requiere caso inválido

---

## 🏁 Estado Final del Pipeline

Todo listo para test-generator. Resumen ejecutivo:

| Etapa | Estado |
|-------|--------|
| Coverage analizado | ✅ (viene de pytest-coverage-analyzer) |
| Plan de pruebas | ✅ N archivos priorizados |
| mock_data.py | ✅ N objetos listos |
| conftest.py | ✅ N fixtures listas |
| Listo para test-generator | ✅ |

Indicar al usuario:
*"Los datos de prueba están completos. Puedes continuar con **test-generator** pasando
este reporte + los archivos del plan, o revisar primero los datos generados en
`tests/mock_data.py`. ¿Continuamos?"*
```

---

## Notas importantes

- **Nunca inventar campos** — siempre leer el schema real antes de generar datos.
- **Fechas fijas, no `datetime.now()`** — los tests deben ser deterministas.
- **No usar `MagicMock` en mock_data.py** — ese archivo es solo para datos/diccionarios.
  Los mocks de servicios externos van en el archivo de test con `@patch` o `AsyncMock`.
- **Spread operator** (`{**USER_VALID, "campo": valor}`) para los objetos inválidos —
  mantiene el resto válido y cambia solo el campo bajo prueba.
- Si el schema tiene **validators personalizados** (`@validator`, `@field_validator`),
  mencionar que esos casos necesitan datos especiales y preguntar al usuario qué validan.
- Consultar `references/pydantic-field-types.md` para casos especiales de tipos.
