from __future__ import annotations

import asyncio
import datetime as dt
import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps_rate_limit import rate_limit_public_read, rate_limit_public_write
from app.core.config import settings
from app.db.session import get_db
from app.ml.predictor import MlbPredictionService
from app.models.mlb import Game, GameFeatureSnapshot, GamePredictionCache, GameWeather
from app.schemas.games import GameDetailResponse, GamesListMeta, GamesListResponse, PredictionResponse
from app.schemas.team_display import team_out_from_model
from app.services.mlb_client import MlbApiClient
from app.services.mlb_sync import sync_games_for_date
from app.services.pipeline_hooks import refresh_prediction_cache_for_games
from app.services.prediction_cache import (
    evaluate_predictions_for_final_games,
    get_cached_prediction,
    upsert_prediction_cache,
)
from app.services.prediction_infer import prediction_response_from_result
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
    *,
    pred_cache_row: GamePredictionCache | None = None,
) -> PredictionResponse | None:
    svc: MlbPredictionService | None = getattr(request.app.state, "prediction_service", None)
    if svc is None:
        return None
    model_version = svc.model_version
    request.app.state.active_model_version = model_version
    if model_version:
        if pred_cache_row is not None and pred_cache_row.model_version == model_version:
            return PredictionResponse(
                game_pk=pred_cache_row.game_pk,
                home_win_probability=pred_cache_row.home_win_probability,
                total_runs_estimate=pred_cache_row.total_runs_estimate,
                over_under_line=pred_cache_row.over_under_line,
                model_version=pred_cache_row.model_version,
                predicted_winner=pred_cache_row.predicted_winner,
                actual_winner=pred_cache_row.actual_winner,
                is_correct=pred_cache_row.is_correct,
                evaluated_at=pred_cache_row.evaluated_at.isoformat()
                if pred_cache_row.evaluated_at
                else None,
            )
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
        out = prediction_response_from_result(pr)
        try:
            await upsert_prediction_cache(session, out, cache_reason)
        except Exception:
            log.warning("prediction cache upsert failed game_pk=%s", game.game_pk, exc_info=True)
        return out
    except Exception:
        log.exception("prediction compute failed game_pk=%s", game.game_pk)
        return None


async def _list_games_impl(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession,
    game_date: dt.date,
    sync: bool,
    fetch_details: bool,
    include_predictions: bool,
) -> GamesListResponse:
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
        try:
            await evaluate_predictions_for_final_games(session, rows)
        except Exception:
            log.warning("evaluate_predictions_for_final_games failed", exc_info=True)
        await session.commit()

    snap_by_pk: dict[int, GameFeatureSnapshot] = {}
    pred_by_pk: dict[int, GamePredictionCache] = {}
    meta_warnings: list[str] = []
    meta_info: list[str] = []
    missing_snapshots: list[int] = []
    if include_predictions and rows:
        pks = [g.game_pk for g in rows]
        res_pc = await session.execute(
            select(GamePredictionCache).where(GamePredictionCache.game_pk.in_(pks))
        )
        for row_pc in res_pc.scalars().all():
            pred_by_pk[row_pc.game_pk] = row_pc
        res_sn = await session.execute(
            select(GameFeatureSnapshot).where(GameFeatureSnapshot.game_pk.in_(pks))
        )
        for s in res_sn.scalars().all():
            snap_by_pk[s.game_pk] = s
        missing_snapshots = [g.game_pk for g in rows if g.game_pk not in snap_by_pk]
        if missing_snapshots:
            sample = ", ".join(str(pk) for pk in missing_snapshots[:5])
            more = f" (+{len(missing_snapshots) - 5} más)" if len(missing_snapshots) > 5 else ""
            log.warning(
                "list_games date=%s: %d partido(s) sin fila en game_feature_snapshots (ej. %s%s). "
                "La inferencia usa valores por defecto (0.5/4.5/ERA default) → P(home) casi igual en todos. "
                "Operaciones → Recalcular indicadores.",
                game_date,
                len(missing_snapshots),
                sample,
                more,
            )
            meta_warnings.append(
                f"{len(missing_snapshots)} partido(s) sin indicadores en BD (game_feature_snapshots) para el "
                f"{game_date.isoformat()}: las estimaciones usan valores por defecto y pueden parecer casi "
                f"iguales. Ejemplos game_pk: {sample}{more}. "
                f"En Operaciones → «Recalcular indicadores»."
            )
    if include_predictions and getattr(request.app.state, "prediction_service", None) is None:
        meta_info.append(
            "Modelo ML no cargado en el API: no hay predicciones nuevas hasta configurar ML_MODEL_PATH y recargar."
        )

    out: list[GameDetailResponse] = []
    for g in rows:
        pred: PredictionResponse | None = None
        if include_predictions:
            pred = await _compute_or_cache_prediction(
                request,
                session,
                g,
                snap_by_pk.get(g.game_pk),
                "list_games",
                pred_cache_row=pred_by_pk.get(g.game_pk),
            )
        out.append(game_detail_response(g, g.weather, pred))
    if sync and rows and settings.pipeline_auto_cache_predictions:
        background_tasks.add_task(
            refresh_prediction_cache_for_games,
            request.app,
            [g.game_pk for g in rows],
            "sync_schedule",
        )
    meta = GamesListMeta(
        warnings=meta_warnings,
        info=meta_info,
        missing_snapshot_count=len(missing_snapshots),
    )
    return GamesListResponse(games=out, meta=meta)


@router.get("/games", response_model=GamesListResponse, dependencies=[Depends(rate_limit_public_read)])
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
) -> GamesListResponse:
    key = (game_date.isoformat(), sync, fetch_details, include_predictions)
    if not hasattr(request.app.state, "games_list_inflight"):
        request.app.state.games_list_inflight = {}
    inflight: dict[tuple[object, ...], asyncio.Task[GamesListResponse]] = (
        request.app.state.games_list_inflight
    )
    if key in inflight:
        return await inflight[key]

    async def _run() -> GamesListResponse:
        return await _list_games_impl(
            request,
            background_tasks,
            session,
            game_date,
            sync,
            fetch_details,
            include_predictions,
        )

    task = asyncio.create_task(_run())
    inflight[key] = task
    try:
        return await task
    finally:
        inflight.pop(key, None)


@router.get(
    "/games/{game_pk}",
    response_model=GameDetailResponse,
    dependencies=[Depends(rate_limit_public_read)],
)
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
        if snap is None:
            log.warning(
                "get_game game_pk=%s sin game_feature_snapshots: predicción con features por defecto. "
                "Recalcular indicadores en Operaciones.",
                game_pk,
            )
        pred = await _compute_or_cache_prediction(request, session, game, snap, "get_game")
    return game_detail_response(game, game.weather, pred)


@router.post(
    "/games/{game_pk}/weather",
    response_model=GameDetailResponse,
    dependencies=[Depends(rate_limit_public_write)],
)
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
