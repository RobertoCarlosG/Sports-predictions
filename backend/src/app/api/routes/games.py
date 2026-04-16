from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.session import get_db
from app.models.mlb import Game, GameWeather
from app.schemas.games import GameDetailResponse
from app.schemas.team_display import team_out_from_model
from app.services.mlb_client import MlbApiClient
from app.services.mlb_sync import sync_games_for_date
from app.services.weather_open_meteo import upsert_weather_for_game

router = APIRouter()


def game_detail_response(game: Game, weather: GameWeather | None) -> GameDetailResponse:
    w_dict: dict[str, object] | None = None
    if weather is not None:
        w_dict = {
            "temperature_c": weather.temperature_c,
            "humidity_pct": weather.humidity_pct,
            "wind_speed_mps": weather.wind_speed_mps,
            "pressure_mbar": weather.pressure_mbar,
            "elevation_m": weather.elevation_m,
            "fetched_at": weather.fetched_at.isoformat(),
        }
    return GameDetailResponse(
        game_pk=game.game_pk,
        season=game.season,
        game_date=game.game_date,
        status=game.status,
        home_team=team_out_from_model(game.home_team),
        away_team=team_out_from_model(game.away_team),
        home_score=game.home_score,
        away_score=game.away_score,
        venue_id=game.venue_id,
        venue_name=game.venue_name,
        lineups=game.lineups_json,
        boxscore=game.boxscore_json,
        weather=w_dict,
    )


@router.get("/games", response_model=list[GameDetailResponse])
async def list_games(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    game_date: Annotated[dt.date, Query(alias="date")],
    sync: Annotated[bool, Query(description="Fetch from MLB API and upsert")] = True,
    fetch_details: Annotated[bool, Query(description="Fetch boxscore and live feed")] = True,
) -> list[GameDetailResponse]:
    client = MlbApiClient(settings.mlb_api_base_url, request.app.state.http_client)
    if sync:
        await sync_games_for_date(
            session,
            client,
            game_date.isoformat(),
            fetch_details=fetch_details,
        )

    result = await session.execute(
        select(Game)
        .where(Game.game_date == game_date)
        .options(
            selectinload(Game.home_team),
            selectinload(Game.away_team),
            selectinload(Game.weather),
        )
    )
    rows = result.scalars().unique().all()
    out: list[GameDetailResponse] = []
    for g in rows:
        out.append(game_detail_response(g, g.weather))
    return out


@router.get("/games/{game_pk}", response_model=GameDetailResponse)
async def get_game(
    game_pk: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GameDetailResponse:
    result = await session.execute(
        select(Game)
        .where(Game.game_pk == game_pk)
        .options(
            selectinload(Game.home_team),
            selectinload(Game.away_team),
            selectinload(Game.weather),
        )
    )
    game = result.scalar_one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return game_detail_response(game, game.weather)


@router.post("/games/{game_pk}/weather", response_model=GameDetailResponse)
async def refresh_weather(
    game_pk: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GameDetailResponse:
    result = await session.execute(
        select(Game)
        .where(Game.game_pk == game_pk)
        .options(
            selectinload(Game.home_team),
            selectinload(Game.away_team),
            selectinload(Game.weather),
        )
    )
    game = result.scalar_one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    await upsert_weather_for_game(
        session,
        game_pk=game_pk,
        venue_id=game.venue_id,
        stadiums_path=settings.mlb_stadiums_path,
        open_meteo_base=settings.open_meteo_base_url,
        client=request.app.state.http_client,
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
    game = result.scalar_one_or_none()
    assert game is not None
    return game_detail_response(game, game.weather)
