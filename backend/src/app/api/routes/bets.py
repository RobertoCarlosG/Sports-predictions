"""API control de apuestas (requiere sesión de usuario / cookie)."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_user import UserIdDep
from app.db.session import get_db
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
from app.services.bets_excel import build_period_workbook_bytes, load_game_labels
from app.models.bets import Bet
from app.services.bets_resolver import compute_bet_outcome, fetch_scores_for_game
from app.services import bets_service

router = APIRouter(prefix="/bets", tags=["bets"])


@router.get("/banks", response_model=list[BetBankOut])
async def list_banks(
    user_id: UserIdDep,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[BetBankOut]:
    return await bets_service.list_banks(session, user_id)


@router.post("/banks", response_model=BetBankOut)
async def create_bank(
    user_id: UserIdDep,
    session: Annotated[AsyncSession, Depends(get_db)],
    body: BetBankCreate,
) -> BetBankOut:
    out = await bets_service.create_bank(session, user_id, body)
    await session.commit()
    return out


@router.put("/banks/{bank_id}", response_model=BetBankOut)
async def update_bank(
    user_id: UserIdDep,
    session: Annotated[AsyncSession, Depends(get_db)],
    bank_id: int,
    body: BetBankUpdate,
) -> BetBankOut:
    out = await bets_service.update_bank(session, user_id, bank_id, body)
    await session.commit()
    return out


@router.get("/periods", response_model=list[BetPeriodOut])
async def list_periods(
    user_id: UserIdDep,
    session: Annotated[AsyncSession, Depends(get_db)],
    bank_id: Annotated[int | None, Query()] = None,
    year: Annotated[int | None, Query()] = None,
) -> list[BetPeriodOut]:
    return await bets_service.list_periods(session, user_id, bank_id=bank_id, year=year)


@router.post("/periods", response_model=BetPeriodOut)
async def create_period(
    user_id: UserIdDep,
    session: Annotated[AsyncSession, Depends(get_db)],
    body: BetPeriodCreate,
) -> BetPeriodOut:
    out = await bets_service.create_period_manual(session, user_id, body)
    await session.commit()
    return out


@router.post("/periods/{period_id}/close", response_model=BetPeriodOut)
async def close_period(
    user_id: UserIdDep,
    session: Annotated[AsyncSession, Depends(get_db)],
    period_id: int,
) -> BetPeriodOut:
    out = await bets_service.close_period(session, user_id, period_id)
    await session.commit()
    return out


@router.get("/periods/{period_id}/stats", response_model=BetPeriodStatsOut)
async def period_stats(
    user_id: UserIdDep,
    session: Annotated[AsyncSession, Depends(get_db)],
    period_id: int,
) -> BetPeriodStatsOut:
    return await bets_service.period_stats(session, user_id, period_id)


@router.get("/periods/{period_id}/export")
async def export_period(
    user_id: UserIdDep,
    session: Annotated[AsyncSession, Depends(get_db)],
    period_id: int,
) -> StreamingResponse:
    period, bets = await bets_service.bets_for_period_export(session, user_id, period_id)
    pks = sorted({b.game_pk for b in bets})
    labels, dates = await load_game_labels(session, pks)
    data = await build_period_workbook_bytes(period, bets, labels, dates)
    fname = f"apuestas-{period.year:04d}-{period.month:02d}.xlsx"
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("", response_model=list[BetOut])
async def list_bets(
    user_id: UserIdDep,
    session: Annotated[AsyncSession, Depends(get_db)],
    bank_id: Annotated[int | None, Query()] = None,
    period_id: Annotated[int | None, Query()] = None,
    game_pk: Annotated[int | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    date_from: Annotated[dt.date | None, Query()] = None,
    date_to: Annotated[dt.date | None, Query()] = None,
) -> list[BetOut]:
    return await bets_service.list_bets(
        session,
        user_id,
        bank_id=bank_id,
        period_id=period_id,
        game_pk=game_pk,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("", response_model=BetOut)
async def create_bet(
    user_id: UserIdDep,
    session: Annotated[AsyncSession, Depends(get_db)],
    body: BetCreate,
) -> BetOut:
    out = await bets_service.create_bet(session, user_id, body)
    await session.commit()
    return out


@router.get("/stats", response_model=BetsStatsOut)
async def bets_stats(
    user_id: UserIdDep,
    session: Annotated[AsyncSession, Depends(get_db)],
    bank_id: Annotated[int | None, Query()] = None,
) -> BetsStatsOut:
    return await bets_service.global_stats(session, user_id, bank_id=bank_id)


@router.get("/{bet_id}", response_model=BetOut)
async def get_bet(
    user_id: UserIdDep,
    session: Annotated[AsyncSession, Depends(get_db)],
    bet_id: int,
) -> BetOut:
    return await bets_service.get_bet(session, user_id, bet_id)


@router.patch("/{bet_id}", response_model=BetOut)
async def patch_bet(
    user_id: UserIdDep,
    session: Annotated[AsyncSession, Depends(get_db)],
    bet_id: int,
    body: BetUpdate,
) -> BetOut:
    out = await bets_service.patch_bet(session, user_id, bet_id, body)
    await session.commit()
    return out


@router.post("/{bet_id}/resolve", response_model=BetOut)
async def resolve_bet(
    user_id: UserIdDep,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    bet_id: int,
) -> BetOut:
    bet = await session.get(Bet, bet_id)
    if bet is None or bet.user_id != user_id:
        raise HTTPException(status_code=404, detail="Apuesta no encontrada.")
    if bet.status != "pending":
        return await bets_service.get_bet(session, user_id, bet_id)

    client = request.app.state.http_client
    hs, aws, src = await fetch_scores_for_game(session, client, bet.game_pk)
    if hs is None or aws is None or src is None:
        return await bets_service.get_bet(session, user_id, bet_id)

    try:
        outcome = compute_bet_outcome(bet, hs, aws)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    bet.status = outcome
    bet.result_source = src
    bet.result_checked_at = dt.datetime.now(dt.UTC)
    await session.commit()
    return await bets_service.get_bet(session, user_id, bet_id)
