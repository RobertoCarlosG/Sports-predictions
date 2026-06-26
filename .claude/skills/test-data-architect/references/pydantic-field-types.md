# Pydantic Field Types — Referencia de Datos de Prueba

## Tipos estándar de Python

| Tipo | Valor válido de ejemplo | Valores inválidos a generar |
|------|------------------------|----------------------------|
| `str` | `"Josh"` | `""`, `None`, `123` (int) |
| `int` | `28` | `"28"` (str), `None`, `28.5` (float) |
| `float` | `9.99` | `"9.99"` (str), `None` |
| `bool` | `True` | `"true"` (str), `1` (int), `None` |
| `list` | `["a", "b"]` | `"a,b"` (str), `None` |
| `dict` | `{"key": "val"}` | `"key=val"` (str), `None` |

---

## Tipos de Pydantic / FastAPI

### EmailStr
```python
# Válido
"josh.dahmer@example.com"

# Inválidos
"notanemail"          # sin @
"@nodomain.com"       # sin usuario
"josh@"               # sin dominio
"josh @example.com"   # espacio
```

### UUID / uuid.UUID
```python
import uuid

# Válido
"550e8400-e29b-41d4-a716-446655440000"
uuid.UUID("550e8400-e29b-41d4-a716-446655440000")

# Inválidos
"not-a-uuid"
"123"
"550e8400-XXXX-41d4-a716-446655440000"  # caracteres inválidos
```

### HttpUrl / AnyUrl
```python
# Válido
"https://example.com/path"

# Inválidos
"not-a-url"
"ftp://invalid"   # si solo acepta http/https
"//missing-scheme.com"
```

### datetime
```python
from datetime import datetime, timezone

# Válido — siempre fechas fijas en tests
datetime(2024, 1, 15, 10, 30, 0)
datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)  # si requiere timezone

# Como string (para JSON body)
"2024-01-15T10:30:00"
"2024-01-15T10:30:00Z"

# Inválidos
"not-a-date"
"2024-13-01"   # mes 13
"01/15/2024"   # formato incorrecto si espera ISO
```

### date
```python
from datetime import date

# Válido
date(2024, 1, 15)
"2024-01-15"

# Inválidos
"15/01/2024"
"2024-13-01"
```

### Decimal
```python
from decimal import Decimal

# Válido
Decimal("9.99")
"9.99"  # Pydantic lo convierte

# Inválidos
"$9.99"  # con símbolo
"nueve"
```

---

## Field Validators / Constraints

### gt, ge, lt, le (numéricos)
```python
# Field(gt=0, lt=120) — mayor que 0, menor que 120
valid: 28          # en el rango medio
invalid_low: 0     # igual al límite inferior (gt, no ge)
invalid_high: 120  # igual al límite superior (lt, no le)
invalid_negative: -1

# Field(ge=1, le=100) — mayor o igual a 1, menor o igual a 100
valid: 50
invalid_low: 0     # por debajo del mínimo (ge=1, entonces 0 es inválido)
invalid_high: 101  # por encima del máximo
```

### min_length, max_length (strings)
```python
# Field(min_length=3, max_length=50)
valid: "Josh"                          # longitud 4
invalid_too_short: "Jo"               # longitud 2 (min_length-1)
invalid_too_long: "J" * 51            # longitud 51 (max_length+1)
invalid_empty: ""                     # longitud 0
```

### pattern / regex
```python
# Field(pattern=r"^\+?[1-9]\d{7,14}$")  — teléfono
valid: "+521234567890"
invalid: "abc"
invalid: "123"          # demasiado corto
invalid: "++1234567890" # doble signo
```

### Literal
```python
# role: Literal["admin", "user", "viewer"]
valid: "user"
invalid: "superadmin"
invalid: "ADMIN"       # case sensitive
invalid: ""
invalid: None
```

---

## Tipos Opcionales

```python
# phone: Optional[str] = None
# NO generar caso inválido — el campo puede estar ausente
# Sí incluir en el objeto VÁLIDO con un valor real: "+52 246 100 0000"
# Probar que se puede omitir en USER_MINIMAL
```

---

## Validators personalizados (@field_validator)

Si el schema tiene validators como:

```python
@field_validator("password")
def password_strength(cls, v):
    if len(v) < 8:
        raise ValueError("password must be at least 8 characters")
    return v
```

Generar:
```python
USER_PASSWORD_INVALID = {**USER_VALID, "password": "short"}  # 5 chars
# El test debe verificar que el error menciona "password" en el detalle
```

**Importante**: Preguntar al usuario si hay validators personalizados en sus schemas
que no sean evidentes del código — pueden tener validaciones de negocio que no están
en los Field() pero sí en métodos `@validator` o `@model_validator`.

---

## Estructura esperada de mock_data.py

```python
# tests/mock_data.py
"""
Datos de prueba para el proyecto [nombre].
NO usar MagicMock aquí — solo datos primitivos y DTOs.
Los mocks de servicios externos van en los archivos de test.
"""

# ══════════════════════════════════════════════════════
# USER — UserCreate schema
# ══════════════════════════════════════════════════════

USER_VALID = {
    "name": "Josh",
    "last_name": "Dahmer",
    "email": "josh.dahmer@example.com",
    "age": 28,
    "role": "user",
    "phone": "+52 246 100 0000"
}

USER_MINIMAL = {
    "name": "Josh",
    "last_name": "Dahmer",
    "email": "josh.dahmer@example.com",
    "age": 28
}

# Inválidos — un campo mal por objeto
USER_NAME_INVALID      = {**USER_VALID, "name": ""}
USER_LASTNAME_INVALID  = {**USER_VALID, "last_name": ""}
USER_EMAIL_INVALID     = {**USER_VALID, "email": "notanemail"}
USER_AGE_INVALID       = {**USER_VALID, "age": 150}
USER_AGE_TYPE_INVALID  = {**USER_VALID, "age": "twenty"}
USER_ROLE_INVALID      = {**USER_VALID, "role": "superadmin"}

# ══════════════════════════════════════════════════════
# PAYMENT — PaymentCreate schema (ejemplo adicional)
# ══════════════════════════════════════════════════════

PAYMENT_VALID = {
    "amount": "99.99",
    "currency": "MXN",
    "user_id": "550e8400-e29b-41d4-a716-446655440000"
}

PAYMENT_AMOUNT_INVALID    = {**PAYMENT_VALID, "amount": "-10.00"}
PAYMENT_CURRENCY_INVALID  = {**PAYMENT_VALID, "currency": "PESOS"}
PAYMENT_USER_ID_INVALID   = {**PAYMENT_VALID, "user_id": "not-a-uuid"}
```
