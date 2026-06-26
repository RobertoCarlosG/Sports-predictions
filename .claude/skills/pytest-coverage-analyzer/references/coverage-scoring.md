# Coverage Scoring — Referencia y Casos Borde

## Ejemplos de cálculo de score

### Ejemplo 1 — Service con 13% cobertura
```
archivo: app/services/user_service.py
cover%: 13%
stmts: 82
tipo: service → multiplicador 3.0

score = (100 - 13) × 3.0 × (82 / 10)
score = 87 × 3.0 × 8.2
score = 2141.4 → normalizado: ~96 → 🔴 Inmediata
```

### Ejemplo 2 — Schema con 60% cobertura
```
archivo: app/schemas/user.py
cover%: 60%
stmts: 23
tipo: schema → multiplicador 1.5

score = (100 - 60) × 1.5 × (23 / 10)
score = 40 × 1.5 × 2.3
score = 138 → normalizado: ~18 → 🟡 Media
```

### Ejemplo 3 — Endpoint con 8% cobertura
```
archivo: app/api/v1/endpoints/payments.py
cover%: 8%
stmts: 56
tipo: endpoint → multiplicador 2.5

score = (100 - 8) × 2.5 × (56 / 10)
score = 92 × 2.5 × 5.6
score = 1288 → normalizado: ~89 → 🔴 Inmediata
```

---

## Normalización de scores

Después de calcular todos los scores raw:
1. Encontrar el score máximo del conjunto
2. `score_normalizado = (score_raw / score_max) × 100`
3. Redondear a entero

---

## Casos borde

### Archivo con 0% y 0 statements
- Ignorar — probablemente es `__init__.py` o archivo vacío
- No incluir en el reporte

### Archivo con 100% coverage
- Marcar como ✅ OK
- No calcular score, no incluir en tablas de prioridad
- Listar al final en sección compacta

### Archivo con cobertura parcial pero tipo "config"
- Aplicar multiplicador 0.3
- Aunque tenga 20% coverage, su score quedará bajo → 🟡 Media o ignorar
- Nota al usuario: "Los archivos de configuración generalmente no requieren pruebas unitarias"

### Varios archivos con el mismo módulo (ej. múltiples services)
- Calcular y ordenar individualmente
- No promediar — cada archivo tiene su propio score

### Proyecto sin ningún test (0% en todo)
- Flag especial: 🚨 PROYECTO SIN COBERTURA
- Recomendar comenzar con tests de integración básicos antes que unitarios
- Sugerir instalar pytest + pytest-cov + httpx como primer paso

---

## Detección de tipo de módulo por path

```python
# Lógica de clasificación (pseudocódigo para Claude)
def classify(path: str) -> tuple[str, float]:
    if "service" in path:
        return "Service", 3.0
    elif "api" in path or "endpoint" in path or "router" in path:
        return "Endpoint/Router", 2.5
    elif "crud" in path or "repositor" in path:
        return "CRUD/Repository", 2.0
    elif "schema" in path:
        return "Schema", 1.5
    elif "model" in path:
        return "Model", 1.2
    elif "util" in path or "helper" in path:
        return "Utility", 1.0
    elif "config" in path or "setting" in path:
        return "Config", 0.3
    else:
        return "Other", 1.0
```

---

## Output del plan — campos requeridos por test-data-architect

Para que la siguiente skill funcione correctamente, el plan de pruebas DEBE incluir
para cada archivo prioritario:

```yaml
# Metadata que test-data-architect necesita
archivo: app/services/user_service.py
tipo: service
schemas_relacionados:
  - app/schemas/user.py        # UserCreate, UserUpdate, UserResponse
  - app/schemas/auth.py        # TokenData
modelos_relacionados:
  - app/models/user.py         # User (SQLAlchemy)
dependencias_a_mockear:
  - app/repositories/user_repo.py
  - app/core/email.py
rutas_relacionadas:             # solo si es endpoint
  - POST /api/v1/users
  - GET /api/v1/users/{id}
```

Incluir este bloque (en formato legible, no necesariamente YAML) en la sección
"Siguiente Paso" del reporte para cada archivo del top 5 de prioridad.
