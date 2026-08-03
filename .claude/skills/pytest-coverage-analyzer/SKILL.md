---
name: pytest-coverage-analyzer
description: >
  Analiza la cobertura de pruebas de un proyecto backend FastAPI ejecutando comandos pytest-cov.
  Pondera cada archivo por criticidad (Inmediata / Alta / Media) y genera un plan de pruebas
  priorizado con desglose por módulo. Usar cuando el usuario quiera saber qué archivos tienen
  poca cobertura, cuáles necesitan atención urgente, o quiera un plan de pruebas estructurado
  para su backend. También se activa cuando el usuario dice "analiza mis pruebas", "qué archivos
  no tienen tests", "dame un plan de testing", o cuando quiere priorizar qué probar primero.
  Esta skill es la entrada del pipeline de testing: su output alimenta a test-data-architect.
---

# Pytest Coverage Analyzer

Analiza cobertura de pruebas en un backend FastAPI/Python, pondera archivos por criticidad y
produce un plan de pruebas priorizado. Es la **primera skill** del pipeline de testing.

```
[pytest-coverage-analyzer] → [test-data-architect] → [test-generator]
         (esta skill)
```

---

## Stage 1: Setup de Coverage

Antes de analizar, verificar si el proyecto tiene configuración de pytest-cov. Si no existe,
crearla como primer paso.

### 1a. Verificar configuración existente

Pedir al usuario que comparta (o explorar con `@` en Claude Code):
- `pyproject.toml`
- `pytest.ini`
- `setup.cfg`

Si **no existe** configuración de coverage, generar este bloque para agregar a `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=app --cov-report=term-missing --cov-report=json:coverage.json --cov-fail-under=0"

[tool.coverage.run]
source = ["app"]
omit = [
    "*/migrations/*",
    "*/alembic/*",
    "app/main.py",          # entry point, no lógica
    "*/config.py",          # configuración, no lógica de negocio
    "**/__init__.py",
]

[tool.coverage.report]
show_missing = true
skip_covered = false
```

Indicar al usuario que ejecute:
```bash
pip install pytest-cov
pytest --cov=app --cov-report=term-missing --cov-report=json:coverage.json
```

Luego pedir que comparta:
1. El output del terminal (tabla de coverage)
2. El archivo `coverage.json` generado

---

## Stage 2: Parsear y Analizar el Reporte

El usuario compartirá el output de pytest. Puede venir en dos formas:

### Forma A — Output de terminal (texto)
```
Name                                    Stmts   Miss  Cover
-----------------------------------------------------------
app/api/v1/endpoints/users.py              45     38     16%
app/services/user_service.py              82     71     13%
app/schemas/user.py                       23      0    100%
```

### Forma B — coverage.json
Buscar el campo `"files"` con estructura:
```json
{
  "files": {
    "app/api/v1/endpoints/users.py": {
      "summary": { "percent_covered": 16.0, "num_statements": 45, "missing_lines": 38 }
    }
  }
}
```

### Extraer para cada archivo:
- Nombre del módulo / path relativo
- `Stmts` (total de líneas ejecutables)
- `Miss` (líneas sin cubrir)
- `Cover` (porcentaje)
- Tipo de módulo (inferir del path: `router/endpoint`, `service`, `schema`, `model`, `util`, `crud`)

---

## Stage 3: Ponderación y Criticidad

Asignar una puntuación de criticidad a cada archivo combinando **cobertura** + **tipo de módulo**.

### Tabla de multiplicadores por tipo de módulo

| Tipo detectado (por path)      | Multiplicador | Razón |
|-------------------------------|--------------|-------|
| `services/` o `*_service.py`  | ×3.0         | Lógica de negocio central |
| `api/` o `endpoints/` o `routers/` | ×2.5    | Contratos públicos de la API |
| `crud/` o `repositories/`     | ×2.0         | Acceso a datos |
| `schemas/`                    | ×1.5         | Validaciones Pydantic |
| `models/`                     | ×1.2         | Definiciones ORM |
| `utils/` o `helpers/`         | ×1.0         | Utilitarios |
| `config/` o `settings/`       | ×0.3         | Excluir de prioridad |

### Fórmula de puntuación

```
score = (100 - cover%) × multiplicador × (stmts / 10)
```

- **Mayor score = más urgente**
- Normalizar scores al rango 0–100 para presentación

### Asignación de prioridad

| Prioridad     | Criterio                                      |
|---------------|-----------------------------------------------|
| 🔴 Inmediata  | Score ≥ 70 O cover% < 20% en módulo crítico   |
| 🟠 Alta       | Score 40–69 O cover% 20–50% en módulo crítico |
| 🟡 Media      | Score < 40 O cover% > 50% pero < 80%          |
| ✅ OK         | cover% ≥ 80%                                  |

---

## Stage 4: Reporte de Cobertura Ponderada

Producir este reporte con los datos analizados:

```
## 📊 Reporte de Cobertura — [nombre del proyecto]

### Resumen General
- Total de archivos analizados: N
- Cobertura promedio del proyecto: X%
- Archivos sin ninguna cobertura: N
- Archivos en estado crítico (< 20%): N

---

### 🔴 Prioridad Inmediata
> Estos archivos bloquean la calidad del sistema. Deben tener pruebas antes de cualquier release.

| Archivo | Cobertura | Líneas sin cubrir | Tipo | Score |
|---------|-----------|-------------------|------|-------|
| app/services/user_service.py | 13% | 71/82 | Service | 94 |
| app/api/v1/endpoints/payments.py | 8% | 52/56 | Endpoint | 91 |

**¿Por qué son críticos?** [Explicación en 1-2 oraciones del riesgo de negocio]

---

### 🟠 Prioridad Alta
> Importantes pero no bloquean. Atender en el siguiente sprint.

| Archivo | Cobertura | Líneas sin cubrir | Tipo | Score |
|---------|-----------|-------------------|------|-------|
| ... | ... | ... | ... | ... |

---

### 🟡 Prioridad Media
> Cobertura parcial. Mejorar cuando los niveles superiores estén atendidos.

| Archivo | Cobertura | Líneas sin cubrir | Tipo | Score |
|---------|-----------|-------------------|------|-------|
| ... | ... | ... | ... | ... |

---

### ✅ Archivos con buena cobertura
[Lista compacta, sin tabla]

---

## 📋 Plan de Pruebas

### Fase 1 — Cobertura de Servicios Críticos (Semana 1-2)
**Objetivo**: Llevar servicios de < 20% a ≥ 60%

1. `app/services/user_service.py`
   - Tests a crear: [lista de funciones/métodos sin cobertura]
   - Dependencias a mockear: [ej. UserRepository, EmailService]
   - Tipos de prueba: unit tests con mocks de repositorio

2. `app/services/payment_service.py`
   - ...

### Fase 2 — Endpoints de API (Semana 2-3)
**Objetivo**: Cubrir contratos públicos con integration tests

1. `app/api/v1/endpoints/users.py`
   - Rutas sin cobertura: GET /users, POST /users, DELETE /users/{id}
   - Datos de prueba necesarios: UserCreateSchema, UserResponseSchema
   - Casos: happy path + validaciones + errores de autenticación

### Fase 3 — Esquemas y Validaciones (Semana 3)
**Objetivo**: Verificar que Pydantic valida correctamente cada campo

1. `app/schemas/user.py`
   - Campos a validar: [lista de campos del schema]
   - Casos: objeto válido completo + cada campo inválido individualmente

---

## 🔗 Siguiente Paso

Este plan está listo para ser procesado por **test-data-architect**.
Archivos prioritarios para preparar datos de prueba:

1. [path/archivo1.py] — requiere: [modelos/schemas que usa]
2. [path/archivo2.py] — requiere: [modelos/schemas que usa]
3. ...

Indicar al usuario: *"¿Continuamos con test-data-architect para preparar los datos de prueba
antes de escribir los tests?"*
```

---

## Notas importantes

- Si el usuario no tiene `tests/` en su proyecto, señalarlo como **bloqueador** antes de continuar.
- Si hay archivos con 0% de cobertura Y son de tipo `service` o `endpoint`, marcarlos como
  🚨 **Sin ninguna prueba** dentro de Prioridad Inmediata.
- El plan de pruebas debe ser **concreto**: mencionar nombres de funciones, rutas, schemas —
  no frases genéricas como "escribir más tests".
- Consultar `references/coverage-scoring.md` para ejemplos de scoring y casos borde.
