"""ORM de NBA (espeja models/mlb.py). Tablas `nba_*` separadas de MLB.

Los IDs de partido de nba_api son strings de 10 caracteres (p. ej. "0022300456"),
por lo que `nba_games.game_id` es VARCHAR y no Integer como `games.game_pk`.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class NbaTeam(Base):
    __tablename__ = "nba_teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # teamId de nba_api
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    abbreviation: Mapped[str] = mapped_column(String(8), nullable=False)
    # Conferencia (East/West) y división; afiliación estática, se rellena en el sync.
    conference: Mapped[str | None] = mapped_column(String(16), nullable=True)
    division: Mapped[str | None] = mapped_column(String(32), nullable=True)


class NbaGame(Base):
    __tablename__ = "nba_games"

    game_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    season: Mapped[str] = mapped_column(String(8), nullable=False)  # "2023-24"
    game_date: Mapped[dt.date] = mapped_column(nullable=False)
    game_datetime_utc: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("nba_teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("nba_teams.id"), nullable=False)
    arena: Mapped[str | None] = mapped_column(String(256), nullable=True)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Stats por equipo del partido (de leaguegamelog): {"home": {...}, "away": {...}}.
    # Alimenta el cálculo de features avanzadas (net rating, pace, eFG%) en snapshots.
    boxscore_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    home_team: Mapped[NbaTeam] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped[NbaTeam] = relationship(foreign_keys=[away_team_id])


class NbaGameFeatureSnapshot(Base):
    """Features almacenadas para entrenamiento / inferencia NBA (1 fila por partido)."""

    __tablename__ = "nba_game_feature_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(
        ForeignKey("nba_games.game_id"), unique=True, nullable=False
    )
    # Forma reciente (ventana rolling)
    home_win_pct_roll: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_win_pct_roll: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_pts_for_roll: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_pts_for_roll: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_pts_against_roll: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_pts_against_roll: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_net_rating_roll: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_net_rating_roll: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_pace_roll: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_pace_roll: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_efg_roll: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_efg_roll: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Descanso / calendario (derivado de game_date previo; sin API extra)
    home_rest_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_rest_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_is_b2b: Mapped[int | None] = mapped_column(Integer, nullable=True)  # back-to-back
    away_is_b2b: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Etiquetas (3 targets); solo en partidos finalizados.
    home_win: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1 home, 0 away
    margin: Mapped[float | None] = mapped_column(Float, nullable=True)  # home - away
    total_points: Mapped[float | None] = mapped_column(Float, nullable=True)  # home + away
    feature_vector_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class NbaGamePredictionCache(Base):
    """Caché de estimaciones NBA (tabla `nba_prediction_results`)."""

    __tablename__ = "nba_prediction_results"

    game_id: Mapped[str] = mapped_column(ForeignKey("nba_games.game_id"), primary_key=True)
    home_win_probability: Mapped[float] = mapped_column(Float, nullable=False)
    margin_estimate: Mapped[float] = mapped_column(Float, nullable=False)
    total_points_estimate: Mapped[float] = mapped_column(Float, nullable=False)
    spread_line: Mapped[float] = mapped_column(Float, nullable=False)
    over_under_line: Mapped[float] = mapped_column(Float, nullable=False)
    over_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    defaults_injected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    trigger_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    computed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    predicted_winner: Mapped[str | None] = mapped_column(String(10), nullable=True)
    actual_winner: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    evaluated_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
