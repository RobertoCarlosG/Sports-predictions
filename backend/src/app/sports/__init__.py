"""Deporte como extensión: cada liga define sus propios campos y consultas.

La API expone rutas por deporte (p. ej. `/api/v1/mlb/...`). Otros deportes pueden
reutilizar el mismo patrón (`history_template.SportHistoryAdapter`) con otros
modelos y parámetros.
"""
