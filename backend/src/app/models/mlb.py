from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    abbreviation: Mapped[str] = mapped_column(String(8), nullable=False)
    venue_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    venue_name: Mapped[str | None] = mapped_column(String(256), nullable=True)


class Game(Base):
    __tablename__ = "games"

    game_pk: Mapped[int] = mapped_column(Integer, primary_key=True)
    season: Mapped[str] = mapped_column(String(8), nullable=False)
    game_date: Mapped[dt.date] = mapped_column(nullable=False)
    game_datetime_utc: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    venue_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    venue_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lineups_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    boxscore_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    home_team: Mapped[Team] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped[Team] = relationship(foreign_keys=[away_team_id])
    weather: Mapped[GameWeather | None] = relationship(back_populates="game", uselist=False)


class GameWeather(Base):
    __tablename__ = "game_weather"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_pk: Mapped[int] = mapped_column(ForeignKey("games.game_pk"), unique=True, nullable=False)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure_mbar: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    game: Mapped[Game] = relationship(back_populates="weather")


class GameFeatureSnapshot(Base):
    """Stored features for ML training / inference (per game)."""

    __tablename__ = "game_feature_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_pk: Mapped[int] = mapped_column(ForeignKey("games.game_pk"), unique=True, nullable=False)
    home_wins_roll: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_wins_roll: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_runs_avg_roll: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_runs_avg_roll: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_win: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1 home, 0 away
    total_runs: Mapped[float | None] = mapped_column(Float, nullable=True)
    feature_vector_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class GamePredictionCache(Base):
    """Caché de estimaciones (tabla `prediction_results`)."""

    __tablename__ = "prediction_results"

    game_pk: Mapped[int] = mapped_column(ForeignKey("games.game_pk"), primary_key=True)
    home_win_probability: Mapped[float] = mapped_column(Float, nullable=False)
    total_runs_estimate: Mapped[float] = mapped_column(Float, nullable=False)
    over_under_line: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    computed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
