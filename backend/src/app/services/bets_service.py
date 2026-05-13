"""CRUD bancos, periodos mensuales y apuestas."""

from __future__ import annotations

import datetime as dt
import calendar
from collections import defaultdict
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bets import Bet, BetBank, BetPeriod
from app.models.mlb import Game
from app.schemas.bets_api import (
    BetBankCreate,
    BetBankOut,
    BetBankUpdate,
    BetCreate,
    BetOut,
    BetPeriodCreate,
    BetPeriodOut,
    BetPeriodStatsOut,
    BetUpdate,
    BetsStatsOut,
)

_MONTHS_ES = (
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
)


def _period_label(year: int, month: int) -> str:
    return f"{_MONTHS_ES[month - 1]} {year}"


def bet_realized_profit(stake: float, odds: float, status: str) -> float:
    if status == "won":
        return float(stake) * (float(odds) - 1.0)
    if status == "lost":
        return -float(stake)
    if status == "push":
        return 0.0
    return 0.0


async def _period_settled_pnl(session: AsyncSession, period_id: int) -> float:
    r = await session.execute(select(Bet).where(Bet.period_id == period_id))
    rows = r.scalars().all()
    return sum(bet_realized_profit(b.stake, b.odds, b.status) for b in rows if b.status in ("won", "lost", "push"))


async def _effective_period_starting_balance(session: AsyncSession, bank: BetBank, period: BetPeriod | None) -> float:
    if period is None:
        return float(bank.initial_amount)
    if period.status == "closed" and period.closing_balance is not None:
        return float(period.closing_balance)
    return float(period.starting_balance) + await _period_settled_pnl(session, period.id)


async def _latest_period_for_bank(session: AsyncSession, bank_id: int) -> BetPeriod | None:
    r = await session.execute(
        select(BetPeriod)
        .where(BetPeriod.bank_id == bank_id)
        .order_by(BetPeriod.year.desc(), BetPeriod.month.desc())
        .limit(1),
    )
    return r.scalar_one_or_none()


async def get_or_create_period_for_bank_month(
    session: AsyncSession,
    user_id: Any,
    bank: BetBank,
    year: int,
    month: int,
) -> BetPeriod:
    r = await session.execute(
        select(BetPeriod).where(
            and_(
                BetPeriod.bank_id == bank.id,
                BetPeriod.year == year,
                BetPeriod.month == month,
            ),
        ),
    )
    existing = r.scalar_one_or_none()
    if existing:
        return existing

    latest = await _latest_period_for_bank(session, bank.id)
    starting = await _effective_period_starting_balance(session, bank, latest)
    period = BetPeriod(
        bank_id=bank.id,
        user_id=user_id,
        name=_period_label(year, month),
        year=year,
        month=month,
        starting_balance=starting,
        status="open",
    )
    session.add(period)
    await session.flush()
    return period


async def list_banks(session: AsyncSession, user_id: Any) -> list[BetBankOut]:
    r = await session.execute(
        select(BetBank).where(BetBank.user_id == user_id).order_by(BetBank.id.asc()),
    )
    return [BetBankOut.model_validate(b) for b in r.scalars().all()]


async def create_bank(session: AsyncSession, user_id: Any, body: BetBankCreate) -> BetBankOut:
    b = BetBank(
        user_id=user_id,
        name=body.name.strip(),
        initial_amount=float(body.initial_amount),
        currency=body.currency.strip() or "USD",
    )
    session.add(b)
    await session.flush()
    return BetBankOut.model_validate(b)


async def update_bank(session: AsyncSession, user_id: Any, bank_id: int, body: BetBankUpdate) -> BetBankOut:
    b = await session.get(BetBank, bank_id)
    if b is None or b.user_id != user_id:
        raise HTTPException(status_code=404, detail="Banco no encontrado.")
    if body.name is not None:
        b.name = body.name.strip()
    if body.is_active is not None:
        b.is_active = body.is_active
    await session.flush()
    return BetBankOut.model_validate(b)


async def list_periods(
    session: AsyncSession,
    user_id: Any,
    *,
    bank_id: int | None,
    year: int | None,
) -> list[BetPeriodOut]:
    q = select(BetPeriod).where(BetPeriod.user_id == user_id)
    if bank_id is not None:
        q = q.where(BetPeriod.bank_id == bank_id)
    if year is not None:
        q = q.where(BetPeriod.year == year)
    q = q.order_by(BetPeriod.year.desc(), BetPeriod.month.desc())
    r = await session.execute(q)
    return [BetPeriodOut.model_validate(p) for p in r.scalars().all()]


async def create_period_manual(session: AsyncSession, user_id: Any, body: BetPeriodCreate) -> BetPeriodOut:
    bank = await session.get(BetBank, body.bank_id)
    if bank is None or bank.user_id != user_id:
        raise HTTPException(status_code=404, detail="Banco no encontrado.")
    r = await session.execute(
        select(BetPeriod).where(
            and_(
                BetPeriod.bank_id == body.bank_id,
                BetPeriod.year == body.year,
                BetPeriod.month == body.month,
            ),
        ),
    )
    if r.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Ya existe un periodo para ese mes y banco.")
    p = await get_or_create_period_for_bank_month(session, user_id, bank, body.year, body.month)
    return BetPeriodOut.model_validate(p)


async def close_period(session: AsyncSession, user_id: Any, period_id: int) -> BetPeriodOut:
    p = await session.get(BetPeriod, period_id)
    if p is None or p.user_id != user_id:
        raise HTTPException(status_code=404, detail="Periodo no encontrado.")
    if p.status == "closed":
        raise HTTPException(status_code=400, detail="El periodo ya está cerrado.")
    pnl = await _period_settled_pnl(session, p.id)
    p.closing_balance = float(p.starting_balance) + pnl
    p.status = "closed"
    p.closed_at = dt.datetime.now(dt.UTC)
    await session.flush()
    return BetPeriodOut.model_validate(p)


async def period_stats(session: AsyncSession, user_id: Any, period_id: int) -> BetPeriodStatsOut:
    p = await session.get(BetPeriod, period_id)
    if p is None or p.user_id != user_id:
        raise HTTPException(status_code=404, detail="Periodo no encontrado.")
    r = await session.execute(select(Bet).where(Bet.period_id == period_id))
    bets = list(r.scalars().all())
    return _build_period_stats(p, bets)


def _build_period_stats(p: BetPeriod, bets: list[Bet]) -> BetPeriodStatsOut:
    total_stake = 0.0
    realized = 0.0
    wins = losses = pushes = pending = 0
    ml_w = ml_l = ou_w = ou_l = 0
    ml_dec = ou_dec = 0
    for b in bets:
        if b.status == "cancelled":
            continue
        total_stake += float(b.stake)
        if b.status == "pending":
            pending += 1
            continue
        realized += bet_realized_profit(b.stake, b.odds, b.status)
        if b.status == "won":
            wins += 1
        elif b.status == "lost":
            losses += 1
        else:
            pushes += 1
        if b.bet_type == "moneyline" and b.status in ("won", "lost"):
            ml_dec += 1
            if b.status == "won":
                ml_w += 1
            else:
                ml_l += 1
        if b.bet_type == "over_under" and b.status in ("won", "lost"):
            ou_dec += 1
            if b.status == "won":
                ou_w += 1
            else:
                ou_l += 1

    decided = wins + losses + pushes
    stake_decided = sum(float(b.stake) for b in bets if b.status in ("won", "lost", "push"))
    roi = (realized / stake_decided * 100.0) if stake_decided > 0 else None
    return BetPeriodStatsOut(
        period_id=p.id,
        name=p.name,
        starting_balance=float(p.starting_balance),
        closing_balance=float(p.closing_balance) if p.closing_balance is not None else None,
        status=p.status,
        total_stake=total_stake,
        realized_pnl=realized,
        roi_pct=roi,
        decided_bets=decided,
        wins=wins,
        losses=losses,
        pushes=pushes,
        pending=pending,
        win_rate_ml_pct=(ml_w / ml_dec * 100.0) if ml_dec else None,
        win_rate_ou_pct=(ou_w / ou_dec * 100.0) if ou_dec else None,
    )


async def list_bets(
    session: AsyncSession,
    user_id: Any,
    *,
    bank_id: int | None,
    period_id: int | None,
    game_pk: int | None,
    status: str | None,
    date_from: dt.date | None,
    date_to: dt.date | None,
) -> list[BetOut]:
    q = (
        select(Bet)
        .options(selectinload(Bet.period))
        .where(Bet.user_id == user_id)
    )
    if bank_id is not None:
        q = q.where(Bet.bank_id == bank_id)
    if period_id is not None:
        q = q.where(Bet.period_id == period_id)
    if game_pk is not None:
        q = q.where(Bet.game_pk == game_pk)
    if status is not None:
        q = q.where(Bet.status == status)
    if date_from is not None or date_to is not None:
        q = q.join(Game, Game.game_pk == Bet.game_pk)
        if date_from is not None:
            q = q.where(Game.game_date >= date_from)
        if date_to is not None:
            q = q.where(Game.game_date <= date_to)
    q = q.order_by(Bet.created_at.desc())
    r = await session.execute(q)
    out: list[BetOut] = []
    for b in r.scalars().unique().all():
        rp = bet_realized_profit(b.stake, b.odds, b.status) if b.status in ("won", "lost", "push") else None
        bo = BetOut.model_validate(b)
        out.append(bo.model_copy(update={"realized_profit": rp}))
    return out


async def create_bet(session: AsyncSession, user_id: Any, body: BetCreate) -> BetOut:
    bank = await session.get(BetBank, body.bank_id)
    if bank is None or bank.user_id != user_id or not bank.is_active:
        raise HTTPException(status_code=404, detail="Banco no encontrado o inactivo.")

    if body.bet_type == "moneyline":
        if body.bet_side not in ("home", "away"):
            raise HTTPException(status_code=400, detail="Moneyline: elige local o visitante.")
    else:
        if body.bet_side not in ("over", "under"):
            raise HTTPException(status_code=400, detail="Más/menos: elige más o menos.")
        if body.ou_line is None:
            raise HTTPException(status_code=400, detail="Más/menos requiere una línea numérica.")

    g = await session.get(Game, body.game_pk)
    if g is None:
        raise HTTPException(status_code=404, detail="Partido no encontrado.")

    y, m = int(g.game_date.year), int(g.game_date.month)
    period = await get_or_create_period_for_bank_month(session, user_id, bank, y, m)

    bet = Bet(
        user_id=user_id,
        bank_id=bank.id,
        period_id=period.id,
        game_pk=body.game_pk,
        bet_type=body.bet_type,
        bet_side=body.bet_side,
        stake=float(body.stake),
        odds=float(body.odds),
        ou_line=float(body.ou_line) if body.ou_line is not None else None,
        notes=body.notes,
    )
    session.add(bet)
    await session.flush()
    return BetOut.model_validate(bet).model_copy(update={"realized_profit": None})


async def get_bet(session: AsyncSession, user_id: Any, bet_id: int) -> BetOut:
    b = await session.get(Bet, bet_id)
    if b is None or b.user_id != user_id:
        raise HTTPException(status_code=404, detail="Apuesta no encontrada.")
    rp = bet_realized_profit(b.stake, b.odds, b.status) if b.status in ("won", "lost", "push") else None
    return BetOut.model_validate(b).model_copy(update={"realized_profit": rp})


async def patch_bet(session: AsyncSession, user_id: Any, bet_id: int, body: BetUpdate) -> BetOut:
    b = await session.get(Bet, bet_id)
    if b is None or b.user_id != user_id:
        raise HTTPException(status_code=404, detail="Apuesta no encontrada.")
    if body.notes is not None:
        b.notes = body.notes
    if body.status == "cancelled":
        if b.status != "pending":
            raise HTTPException(status_code=400, detail="Solo se pueden cancelar apuestas pendientes.")
        b.status = "cancelled"
    await session.flush()
    rp = bet_realized_profit(b.stake, b.odds, b.status) if b.status in ("won", "lost", "push") else None
    return BetOut.model_validate(b).model_copy(update={"realized_profit": rp})


async def global_stats(
    session: AsyncSession,
    user_id: Any,
    *,
    bank_id: int | None,
) -> BetsStatsOut:
    q = select(Bet).where(Bet.user_id == user_id)
    if bank_id is not None:
        q = q.where(Bet.bank_id == bank_id)
    r = await session.execute(q)
    bets = list(r.scalars().all())
    total_stake = 0.0
    realized = 0.0
    wins = losses = pushes = pending = 0
    by_type: dict[str, dict[str, float | int | None]] = defaultdict(
        lambda: {"stake": 0.0, "pnl": 0.0, "decided": 0, "wins": 0},
    )
    stake_decided = 0.0
    for b in bets:
        if b.status == "cancelled":
            continue
        total_stake += float(b.stake)
        by_type[b.bet_type]["stake"] = float(by_type[b.bet_type]["stake"]) + float(b.stake)
        if b.status == "pending":
            pending += 1
            continue
        pnl = bet_realized_profit(b.stake, b.odds, b.status)
        realized += pnl
        stake_decided += float(b.stake)
        by_type[b.bet_type]["pnl"] = float(by_type[b.bet_type]["pnl"]) + pnl
        if b.status in ("won", "lost"):
            by_type[b.bet_type]["decided"] = int(by_type[b.bet_type]["decided"]) + 1
            if b.status == "won":
                by_type[b.bet_type]["wins"] = int(by_type[b.bet_type]["wins"]) + 1
        if b.status == "won":
            wins += 1
        elif b.status == "lost":
            losses += 1
        else:
            pushes += 1

    roi = (realized / stake_decided * 100.0) if stake_decided > 0 else None
    return BetsStatsOut(
        total_stake=total_stake,
        realized_pnl=realized,
        roi_pct=roi,
        decided_bets=wins + losses + pushes,
        wins=wins,
        losses=losses,
        pushes=pushes,
        pending=pending,
        by_type=dict(by_type),
    )


async def bets_for_period_export(session: AsyncSession, user_id: Any, period_id: int) -> tuple[BetPeriod, list[Bet]]:
    p = await session.get(BetPeriod, period_id)
    if p is None or p.user_id != user_id:
        raise HTTPException(status_code=404, detail="Periodo no encontrado.")
    r = await session.execute(
        select(Bet).where(Bet.period_id == period_id).order_by(Bet.created_at.asc()),
    )
    return p, list(r.scalars().all())
