"""ORM para control de apuestas (migración 007_app_users_and_bets.sql)."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    pass


class AppUser(Base):
    __tablename__ = "app_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    google_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    picture_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    banks: Mapped[list[BetBank]] = relationship(back_populates="user", cascade="all, delete-orphan")


class BetBank(Base):
    __tablename__ = "bet_banks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    initial_amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, server_default="USD")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user: Mapped[AppUser] = relationship(back_populates="banks")
    periods: Mapped[list[BetPeriod]] = relationship(back_populates="bank", cascade="all, delete-orphan")
    bets: Mapped[list[Bet]] = relationship(back_populates="bank")


class BetPeriod(Base):
    __tablename__ = "bet_periods"
    __table_args__ = (UniqueConstraint("bank_id", "year", "month", name="ux_bet_periods_bank_year_month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bank_id: Mapped[int] = mapped_column(Integer, ForeignKey("bet_banks.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    starting_balance: Mapped[float] = mapped_column(Float, nullable=False)
    closing_balance: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="open")
    closed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    bank: Mapped[BetBank] = relationship(back_populates="periods")
    bets: Mapped[list[Bet]] = relationship(back_populates="period")


class Bet(Base):
    __tablename__ = "bets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False)
    bank_id: Mapped[int] = mapped_column(Integer, ForeignKey("bet_banks.id", ondelete="CASCADE"), nullable=False)
    period_id: Mapped[int] = mapped_column(Integer, ForeignKey("bet_periods.id", ondelete="RESTRICT"), nullable=False)
    game_pk: Mapped[int] = mapped_column(Integer, ForeignKey("games.game_pk", ondelete="RESTRICT"), nullable=False)
    bet_type: Mapped[str] = mapped_column(String(16), nullable=False)
    bet_side: Mapped[str] = mapped_column(String(16), nullable=False)
    stake: Mapped[float] = mapped_column(Float, nullable=False)
    odds: Mapped[float] = mapped_column(Float, nullable=False)
    ou_line: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    result_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    result_checked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    bank: Mapped[BetBank] = relationship(back_populates="bets")
    period: Mapped[BetPeriod] = relationship(back_populates="bets")
