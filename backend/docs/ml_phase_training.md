# Fase 1: Entrenamiento del Modelo (Training)

El proceso de entrenamiento convierte los datos históricos capturados en la base de datos de PostgreSQL en un modelo empaquetado y listo para estimar. Esta fase suele ejecutarse ya sea como tarea manual desde el Panel de Operaciones del sistema, o como un script programado (`python -m app.ml.train_from_db`).

## Explicación Técnica

1. **Recopilación de Conjunto de Datos (Dataset)**:
   Se hace un Query en SQLAlchemy cruzando `GameFeatureSnapshot`, `Game`, y `GameWeather`.
   Solo se toman los registros que tienen resultados efectivos observados (etiquetas no-nulas: `home_win` y `total_runs`).
2. **Construcción de Matriz**:
   Se pasa cada partido por la función `build_feature_values_for_training` que alinea las variables, imputa valores por defecto cuando falta algún dato (por ejemplo, si no hay clima, usa `20°C` y `50%` de humedad) y marca el flag `defaults_injected = 1`.
3. **Validación Temporal**:
   No se usa partición aleatoria convencional (Train/Test split) para evitar "data leakage" (fuga de datos futuros al pasado). Se divide temporalmente: los partidos jugados antes de una fecha (`--val-from`) van a entrenamiento y los partidos en/después de esa fecha van a evaluación.
4. **Ensamblaje**:
   Se entrenan dos objetos de *Scikit-Learn*: `RandomForestClassifier` (clasificación binaria victoria/derrota) y `RandomForestRegressor` (regresión continua para carreras totales).
5. **Empaquetado (Bundle)**:
   Se serializan los modelos junto con los metadatos de validación (Accuracy, Mean Absolute Error) y la versión solicitada dentro de un archivo `model.joblib`.

## Diagrama de Flujo del Entrenamiento

```mermaid
flowchart TD
    Start[Inicio Script de Entrenamiento] --> QueryDB[Consultar Base de Datos<br>(Games + Snapshots + Weather)]
    QueryDB --> ValRows{¿Suficientes registros?}
    ValRows -- No (<20) --> Error[Lanzar RuntimeError]
    ValRows -- Sí --> Transform[Transformar datos en Matrices Numpy X, Y]
    Transform --> Impute[Imputar datos faltantes<br>y activar 'defaults_injected']
    Impute --> Split[División Temporal<br>Train vs Validation]
    Split --> FitClf[Fit RandomForestClassifier<br>X_train, Y_home]
    Split --> FitReg[Fit RandomForestRegressor<br>X_train, Y_runs]
    FitClf --> Metrics[Evaluar en X_val<br>Accuracy, MAE, Proba STD]
    FitReg --> Metrics
    Metrics --> Bundle[Empaquetar Clasificador, Regresor y Metadatos]
    Bundle --> SaveDB[joblib.dump en /artifacts/model.joblib]
    SaveDB --> End[Fin del Entrenamiento]
```
