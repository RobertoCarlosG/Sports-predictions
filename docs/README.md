# Documentación — Sports-Predictions

Índice de la documentación del monorepo. Las reglas de estilo y contexto compartido del workspace padre siguen en `../../docs/` (p. ej. [estilo-programacion.md](../../docs/estilo-programacion.md)).

## Empezar por aquí

| Documento | Cuándo leerlo |
|-----------|---------------|
| [vision-y-alcance.md](vision-y-alcance.md) | Qué es el proyecto, objetivos, contexto técnico y resumen de lo implementado. **Punto de entrada recomendado.** |
| [estatus-actual.md](estatus-actual.md) | Detalle de APIs, esquemas, flujos de datos, pantallas, tests y despliegue. |
| [estado-real-mvp1.md](estado-real-mvp1.md) | **Auditoría honesta**: gaps entre lo que dicen los docs y lo que hay en código. Lectura obligatoria antes de planear. |
| [proximos-pasos.md](proximos-pasos.md) | Roadmap operativo y plan PR1 → PR2 → PR3 para cerrar el MVP-1. |
| [pendientes.md](pendientes.md) | Pendientes de producto y decisiones abiertas (no técnicas). |

## Detalle técnico y operación

| Documento | Contenido |
|-----------|-----------|
| [diseno-pipeline-predicciones.md](diseno-pipeline-predicciones.md) | Arquitectura del pipeline ingesta → features → entrenamiento → inferencia, con etapas A-D marcadas. |
| [Comportamiento-predicciones.md](Comportamiento-predicciones.md) | Lógica de visualización Hit/Miss, contratos DTO reales (`GameDetail`, `PredictionOut`). |
| [pendientes-sync-boxscore.md](pendientes-sync-boxscore.md) | Historial técnico: sync por rango, por partido, box score, lineups, backfill admin, ETL diario. |
| [migraciones.md](migraciones.md) | Detalle de cada `00*_*.sql`, dependencias y troubleshooting. |
| [deploy.md](deploy.md) | Supabase, Render, Vercel, CORS, verificación. |
| [errores_direct_connection.md](errores_direct_connection.md) | Pooler transaccional de Supabase, IPv4 y `DATABASE_URL` con Render. |
| [UI_DESING_STANDARDS.md](UI_DESING_STANDARDS.md) | Estándares visuales del dashboard. |

## Histórico y notas de sesión

| Documento | Contenido |
|-----------|-----------|
| [SESSION-SUMMARY-2026-04-23.md](SESSION-SUMMARY-2026-04-23.md) | Resumen de mejoras del 2026-04-23 (evaluación, signals, lock contention). Algunas guías referenciadas en su sección "Documentación creada" no se versionaron — el contenido vive en los archivos principales actualizados. |

**README del monorepo:** [../README.md](../README.md) (inicio rápido local).
**SQL del backend:** [../backend/sql/README.md](../backend/sql/README.md) (orden de aplicación).
