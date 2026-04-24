from __future__ import annotations

import datetime as dt
import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.session import get_db
from app.ml.predictor import MlbPredictionService
from app.models.mlb import Game, GameFeatureSnapshot, GameWeather
from app.schemas.games import GameDetailResponse, PredictionResponse
from app.schemas.team_display import team_out_from_model
from app.services.mlb_client import MlbApiClient
from app.services.mlb_sync import sync_games_for_date
from app.services.pipeline_hooks import refresh_prediction_cache_for_games
from app.services.prediction_cache import get_cached_prediction, upsert_prediction_cache, evaluate_prediction
from app.services.weather_open_meteo import upsert_weather_for_game

log = logging.getLogger(__name__)
router = APIRouter()


def game_detail_response(
    game: Game,
    weather: GameWeather | None,
    prediction: PredictionResponse | None = None,
) -> GameDetailResponse:
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
        prediction=prediction,
    )


async def _compute_or_cache_prediction(
    request: Request,
    session: AsyncSession,
    game: Game,
    snapshot: GameFeatureSnapshot | None,
    cache_reason: str,
) -> PredictionResponse | None:
    svc: MlbPredictionService | None = getattr(request.app.state, "prediction_service", None)
    if svc is None:
        return None
    model_version: str = getattr(request.app.state, "active_model_version", "") or ""
    if model_version:
        cached = await get_cached_prediction(session, game.game_pk, model_version)
        if cached is not None:
            return cached
    
    now = dt.datetime.now(dt.timezone.utc)
    game_is_future = False
    
    if game.game_datetime_utc is not None:
        if game.game_datetime_utc.tzinfo is None:
            game_dt = game.game_datetime_utc.replace(tzinfo=dt.timezone.utc)
        else:
            game_dt = game.game_datetime_utc
        game_is_future = game_dt > now
    else:
        today = now.date()
        game_is_future = game.game_date > today
    
    game_status_lower = game.status.lower()
    game_is_live_or_scheduled = any(
        status in game_status_lower
        for status in ["scheduled", "pre-game", "warmup", "in progress", "live", "delayed"]
    )
    
    should_predict = game_is_future or game_is_live_or_scheduled
    
    if not should_predict:
        log.info(
            "game_pk=%s is in the past (date=%s, status=%s) with no cached prediction, skipping prediction",
            game.game_pk,
            game.game_date,
            game.status,
        )
        return None
    
    try:
        pr = svc.predict(game, game.weather, snapshot)
        out = PredictionResponse(
            game_pk=pr.game_pk,
            home_win_probability=pr.home_win_probability,
            total_runs_estimate=pr.total_runs_estimate,
            over_under_line=pr.over_under_line,
            model_version=pr.model_version,
        )
        try:
            await upsert_prediction_cache(session, out, cache_reason)
        except Exception:
            log.warning("prediction cache upsert failed game_pk=%s", game.game_pk, exc_info=True)
        return out
    except Exception:
        log.exception("prediction compute failed game_pk=%s", game.game_pk)
        return None


@router.get("/games", response_model=list[GameDetailResponse])
async def list_games(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db)],
    game_date: Annotated[dt.date, Query(alias="date")],
    sync: Annotated[bool, Query(description="Fetch from MLB API and upsert")] = True,
    fetch_details: Annotated[bool, Query(description="Fetch boxscore and live feed")] = True,
    include_predictions: Annotated[
        bool,
        Query(
            description="Incluir estimación ML por partido (misma lógica que GET /predict/{game_pk})."
        ),
    ] = True,
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
    
    if sync and rows:
        for g in rows:
            game_status_lower = g.status.lower()
            is_final = any(status in game_status_lower for status in ["final", "completed", "game over"])
            if is_final and g.home_score is not None and g.away_score is not None:
                try:
                    await evaluate_prediction(session, g.game_pk)
                except Exception:
                    log.warning("Failed to evaluate prediction for game_pk=%s", g.game_pk, exc_info=True)
        await session.commit()
    
    snap_by_pk: dict[int, GameFeatureSnapshot] = {}
    if include_predictions and rows:
        pks = [g.game_pk for g in rows]
        res_sn = await session.execute(
            select(GameFeatureSnapshot).where(GameFeatureSnapshot.game_pk.in_(pks))
        )
        for s in res_sn.scalars().all():
            snap_by_pk[s.game_pk] = s

    out: list[GameDetailResponse] = []
    for g in rows:
        pred: PredictionResponse | None = None
        if include_predictions:
            pred = await _compute_or_cache_prediction(
                request, session, g, snap_by_pk.get(g.game_pk), "list_games"
            )
        out.append(game_detail_response(g, g.weather, pred))
    if sync and rows and settings.pipeline_auto_cache_predictions:
        background_tasks.add_task(
            refresh_prediction_cache_for_games,
            request.app,
            [g.game_pk for g in rows],
            "sync_schedule",
        )
    return out


@router.get("/games/{game_pk}", response_model=GameDetailResponse)
async def get_game(
    request: Request,
    game_pk: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    include_predictions: Annotated[
        bool,
        Query(
            description="Incluir estimación ML (misma lógica que GET /predict/{game_pk}).",
        ),
    ] = True,
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
    pred: PredictionResponse | None = None
    if include_predictions:
        snap_row = await session.execute(
            select(GameFeatureSnapshot).where(GameFeatureSnapshot.game_pk == game_pk)
        )
        snap = snap_row.scalar_one_or_none()
        pred = await _compute_or_cache_prediction(request, session, game, snap, "get_game")
    return game_detail_response(game, game.weather, pred)


@router.post("/games/{game_pk}/weather", response_model=GameDetailResponse)
async def refresh_weather(
    game_pk: int,
    request: Request,
    background_tasks: BackgroundTasks,
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
    if settings.pipeline_auto_cache_predictions:
        background_tasks.add_task(
            refresh_prediction_cache_for_games,
            request.app,
            [game_pk],
            "weather_refresh",
        )
    return game_detail_response(game, game.weather)
