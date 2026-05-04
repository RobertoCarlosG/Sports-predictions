# Visión General del Algoritmo de Predicción (Machine Learning)

El motor de predicciones de la aplicación está construido en Python utilizando **scikit-learn**. Su objetivo principal es estimar dos resultados para cualquier partido de la MLB:
1. **Probabilidad de victoria del equipo local** (`home_win_probability`), utilizando un `RandomForestClassifier`.
2. **Estimación total de carreras** (`total_runs_estimate` y `over_under_line`), utilizando un `RandomForestRegressor`.

El modelo utiliza 13 variables predictoras (features) extraídas de la base de datos (rendimiento reciente de los equipos, efectividad de los lanzadores y condiciones climáticas).

## Diagrama de Clases del Subsistema ML

A continuación se muestra un diagrama de clases que detalla las estructuras de datos, las clases del modelo de dominio y la clase de servicio que encapsula la inferencia de Scikit-Learn.

```mermaid
classDiagram
    class Game {
        +int game_pk
        +str season
        +date game_date
        +datetime game_datetime_utc
        +str status
        +int home_score
        +int away_score
    }
    
    class GameFeatureSnapshot {
        +int game_pk
        +float home_wins_roll
        +float away_wins_roll
        +float home_runs_avg_roll
        +float away_runs_avg_roll
        +float home_starter_era
        +float away_starter_era
        +float home_bullpen_era
        +float away_bullpen_era
    }
    
    class GameWeather {
        +float temperature_c
        +float humidity_pct
        +float wind_speed_mps
        +float elevation_m
    }

    class PredictionResult {
        <<dataclass>>
        +int game_pk
        +float home_win_probability
        +float total_runs_estimate
        +float over_under_line
        +str model_version
    }

    class MlbPredictionService {
        -Path _model_path
        -dict _bundle
        -Signature _signature
        +str model_version
        +reload() dict
        +predict(Game, GameWeather, GameFeatureSnapshot) PredictionResult
    }

    class ScikitLearnBundle {
        <<joblib>>
        +RandomForestClassifier clf
        +RandomForestRegressor reg
        +list[str] feature_names
        +str model_version
        +str training_meta
    }

    Game "1" -- "0..1" GameFeatureSnapshot : Contexto estadístico
    Game "1" -- "0..1" GameWeather : Contexto ambiental
    MlbPredictionService ..> ScikitLearnBundle : Carga desde disco
    MlbPredictionService ..> PredictionResult : Retorna
```

## Flujo General del Sistema (Macro-Proceso)

Este diagrama grande ilustra el ciclo de vida completo del algoritmo ML en el backend, desde la preparación y el entrenamiento hasta la inferencia y almacenamiento del resultado.

```mermaid
sequenceDiagram
    participant ETL as Pipeline ETL (Snapshots)
    participant Train as Entrenamiento (train_from_db.py)
    participant Model as Archivo (.joblib)
    participant Pred as MlbPredictionService
    participant Cache as DB (GamePredictionCache)
    
    %% Fase de Preparación
    rect rgb(200, 220, 240)
    note right of ETL: 1. PREPARACIÓN DE DATOS (Background)
    ETL->>ETL: Descarga partidos y resultados
    ETL->>ETL: Calcula ERA, promedios y rachas
    ETL->>DB: Guarda GameFeatureSnapshot
    end
    
    %% Fase de Entrenamiento
    rect rgb(220, 240, 200)
    note right of Train: 2. ENTRENAMIENTO DEL MODELO (Admin Panel)
    Train->>DB: Query(Game, Snapshot, Weather)
    Train->>Train: Extrae Matriz X (13 features) y Y (win, runs)
    Train->>Train: Partición temporal (Train / Validation)
    Train->>Train: Entrena RandomForestClassifier & Regressor
    Train->>Train: Evalúa Accuracy y MAE
    Train->>Model: Serializa (joblib.dump)
    end
    
    %% Fase de Inferencia
    rect rgb(240, 220, 200)
    note right of Pred: 3. INFERENCIA Y CACHÉ (API Calls)
    Pred->>Model: joblib.load(model.joblib)
    Pred->>DB: Obtener Game, Weather, Snapshot
    Pred->>Pred: Alinea Matriz X (13 dimensiones)
    Pred->>Pred: Llama clf.predict_proba() y reg.predict()
    Pred->>Cache: Upsert PredictionResponse
    Cache-->>Pred: Retorna a la interfaz del usuario
    end
```

## Detalles Técnicos
- **Variables (Features):** `home_wins_roll`, `away_wins_roll`, `home_runs_avg_roll`, `away_runs_avg_roll`, `temperature_c`, `humidity_pct`, `wind_speed_mps`, `elevation_m`, `home_starter_era`, `away_starter_era`, `home_bullpen_era`, `away_bullpen_era`, y una variable categórica booleana (`defaults_injected`) que permite al Random Forest aprender a ajustar sus ramas cuando hay falta de datos (e.g. sin clima o ERA disponible).
- **Manejo de estados:** Se usa una firma combinada del sistema de archivos (`mtime_ns` y `size`) en el `MlbPredictionService` para realizar una recarga perezosa del modelo en memoria, evitando tiempos de inactividad durante las inferencias y permitiendo que la recarga ocurra "en caliente".
