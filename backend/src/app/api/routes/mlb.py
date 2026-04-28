from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps_rate_limit import rate_limit_public_api
from app.core.config import settings
from app.db.session import get_db
from app.models.mlb import Game, Team
from app.schemas.games import GameDetailResponse, TeamOut
from app.schemas.team_display import team_out_from_model
from app.schemas.history import (
    HistoryGameOut,
    MlbSyncGameBody,
    MlbSyncRangeBody,
    MlbSyncRangeResponse,
)
from app.services.mlb_client import MlbApiClient
from app.services.mlb_history import compute_winner_team_id, query_mlb_history
from app.services.mlb_sync import sync_games_for_date, sync_single_game
from app.services.pipeline_hooks import refresh_prediction_cache_for_games
from app.api.routes.games import game_detail_response

router = APIRouter(prefix="/mlb", tags=["mlb"])

_MAX_SYNC_DAYS = 370
# Evita timeouts del proxy (p. ej. Render) al procesar muchos días en una sola petición.
_MAX_SYNC_DAYS_PER_REQUEST = 7


@router.get("/teams", response_model=list[TeamOut])
async def list_mlb_teams(session: Annotated[AsyncSession, Depends(get_db)]) -> list[TeamOut]:
    result = await session.execute(select(Team).order_by(Team.abbreviation))
    return [team_out_from_model(t) for t in result.scalars().all()]


@router.get("/history/games", response_model=list[HistoryGameOut])
async def list_mlb_history(
    session: Annotated[AsyncSession, Depends(get_db)],
    season: Annotated[str | None, Query(description="Filtrar por temporada (ej. 2024)")] = None,
    team_id: Annotated[int | None, Query(description="Partidos donde juega este equipo")] = None,
    date_from: Annotated[dt.date | None, Query(alias="from")] = None,
    date_to: Annotated[dt.date | None, Query(alias="to")] = None,
    only_final: Annotated[bool, Query(description="Solo partidos con estado Final")] = False,
    only_with_scores: Annotated[
        bool,
        Query(description="Solo partidos con marcador persistido"),
    ] = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[HistoryGameOut]:
    games = await query_mlb_history(
        session,
        season=season,
        team_id=team_id,
        date_from=date_from,
        date_to=date_to,
        only_final=only_final,
        only_with_scores=only_with_scores,
        limit=limit,
        offset=offset,
    )
    out: list[HistoryGameOut] = []
    for g in games:
        hid = g.home_team_id
        aid = g.away_team_id
        hs = g.home_score
        aws = g.away_score
        out.append(
            HistoryGameOut(
                sport_code="mlb",
                game_pk=g.game_pk,
                season=g.season,
                game_date=g.game_date,
                status=g.status,
                home_team=team_out_from_model(g.home_team),
                away_team=team_out_from_model(g.away_team),
                home_score=hs,
                away_score=aws,
                winner_team_id=compute_winner_team_id(hid, aid, hs, aws),
            )
        )
    return out


@router.post("/sync-range", response_model=MlbSyncRangeResponse, dependencies=[Depends(rate_limit_public_api)])
async def sync_mlb_date_range(
    body: MlbSyncRangeBody,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MlbSyncRangeResponse:
    if body.end_date < body.start_date:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date")
    delta = (body.end_date - body.start_date).days + 1
    if delta > _MAX_SYNC_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Range too large (max {_MAX_SYNC_DAYS} days)",
        )
    if delta > _MAX_SYNC_DAYS_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Sync at most {_MAX_SYNC_DAYS_PER_REQUEST} calendar days per request "
                "(split the range or use single-game sync)."
            ),
        )
    client = MlbApiClient(settings.mlb_api_base_url, request.app.state.http_client)
    d = body.start_date
    while d <= body.end_date:
        await sync_games_for_date(
            session,
            client,
            d.isoformat(),
            fetch_details=body.fetch_details,
        )
        d += dt.timedelta(days=1)
    if settings.pipeline_auto_cache_predictions:
        pk_result = await session.execute(
            select(Game.game_pk).where(
                Game.game_date >= body.start_date,
                Game.game_date <= body.end_date,
            )
        )
        pks = [row[0] for row in pk_result.all()]
        if pks:
            background_tasks.add_task(
                refresh_prediction_cache_for_games,
                request.app,
                pks,
                "sync_range",
            )
    return MlbSyncRangeResponse(
        start_date=body.start_date,
        end_date=body.end_date,
        days_synced=delta,
    )


@router.post("/games/{game_pk}/sync", response_model=GameDetailResponse, dependencies=[Depends(rate_limit_public_api)])
async def sync_mlb_single_game(
    game_pk: int,
    body: MlbSyncGameBody,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GameDetailResponse:
    client = MlbApiClient(settings.mlb_api_base_url, request.app.state.http_client)
    game = await sync_single_game(
        session,
        client,
        game_pk,
        fetch_details=body.fetch_details,
    )
    if game is None:
        raise HTTPException(
            status_code=404,
            detail="Game not found in MLB schedule for this game_pk",
        )
    result = await session.execute(
        select(Game)
        .where(Game.game_pk == game_pk)
        .options(
            selectinload(Game.home_team),
            selectinload(Game.away_team),
            selectinload(Game.weather),
        )
    )
    row = result.scalar_one_or_none()
    assert row is not None
    if settings.pipeline_auto_cache_predictions:
        background_tasks.add_task(
            refresh_prediction_cache_for_games,
            request.app,
            [game_pk],
            "sync_single",
        )
    return game_detail_response(row, row.weather)


@router.get("/history/games/{game_pk}", response_model=HistoryGameOut)
async def get_mlb_history_one(
    game_pk: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HistoryGameOut:
    result = await session.execute(
        select(Game)
        .where(Game.game_pk == game_pk)
        .options(selectinload(Game.home_team), selectinload(Game.away_team))
    )
    g = result.scalar_one_or_none()
    if g is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return HistoryGameOut(
        sport_code="mlb",
        game_pk=g.game_pk,
        season=g.season,
        game_date=g.game_date,
        status=g.status,
        home_team=team_out_from_model(g.home_team),
        away_team=team_out_from_model(g.away_team),
        home_score=g.home_score,
        away_score=g.away_score,
        winner_team_id=compute_winner_team_id(
            g.home_team_id, g.away_team_id, g.home_score, g.away_score
        ),
    )
