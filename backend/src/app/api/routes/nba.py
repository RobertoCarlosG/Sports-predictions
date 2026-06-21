from __future__ import annotations

import datetime as dt
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps_rate_limit import rate_limit_public_read, rate_limit_public_write
from app.db.session import get_db
from app.ml.model_routing import (
    DEFAULT_NBA_MODEL,
    NbaModelKind,
    get_nba_prediction_service,
    get_nba_prediction_service_optional,
)
from app.models.nba import NbaGame, NbaGameFeatureSnapshot, NbaTeam
from app.schemas.nba import (
    NbaGameDetailResponse,
    NbaGamesListMeta,
    NbaGamesListResponse,
    NbaPredictionResponse,
    NbaTeamOut,
)
from app.core.config import settings
from app.services.nba_client import NbaApiClient
from app.services.nba_prediction_cache import (
    evaluate_nba_predictions_for_final_games,
    get_cached_nba_prediction,
    prediction_response_from_result,
    upsert_nba_prediction_cache,
)
from app.services.nba_sync import sync_games_for_date, sync_season

log = logging.getLogger(__name__)


def _require_nba_enabled() -> None:
    if not settings.nba_enabled:
        raise HTTPException(status_code=503, detail="NBA feature is currently disabled.")


router = APIRouter(dependencies=[Depends(_require_nba_enabled)])


def _team_out(team: NbaTeam) -> NbaTeamOut:
    return NbaTeamOut.model_validate(team)


def _game_detail(
    game: NbaGame,
    prediction: NbaPredictionResponse | None = None,
    *,
    include_payload: bool = True,
) -> NbaGameDetailResponse:
    return NbaGameDetailResponse(
        game_id=game.game_id,
        season=game.season,
        game_date=game.game_date,
        status=game.status,
        home_team=_team_out(game.home_team),
        away_team=_team_out(game.away_team),
        home_score=game.home_score,
        away_score=game.away_score,
        arena=game.arena,
        boxscore=game.boxscore_json if include_payload else None,
        prediction=prediction,
    )


async def _compute_or_cache_prediction(
    request: Request,
    session: AsyncSession,
    game: NbaGame,
    snapshot: NbaGameFeatureSnapshot | None,
    cache_reason: str,
    *,
    model: NbaModelKind = DEFAULT_NBA_MODEL,
) -> NbaPredictionResponse | None:
    svc = get_nba_prediction_service_optional(request, model)
    if svc is None:
        return None
    model_version = svc.model_version
    if model_version:
        cached = await get_cached_nba_prediction(session, game.game_id, model_version)
        if cached is not None:
            return cached
    try:
        result = svc.predict(game.game_id, snapshot)
        out = prediction_response_from_result(result)
        try:
            await upsert_nba_prediction_cache(session, out, cache_reason)
        except Exception:
            log.warning("nba prediction cache upsert failed game=%s", game.game_id, exc_info=True)
        return out
    except Exception:
        log.exception("nba prediction compute failed game=%s", game.game_id)
        return None


@router.get(
    "/nba/teams",
    response_model=list[NbaTeamOut],
    dependencies=[Depends(rate_limit_public_read)],
)
async def list_nba_teams(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[NbaTeamOut]:
    rows = (await session.execute(select(NbaTeam).order_by(NbaTeam.abbreviation))).scalars().all()
    return [_team_out(t) for t in rows]


@router.get(
    "/nba/games",
    response_model=NbaGamesListResponse,
    dependencies=[Depends(rate_limit_public_read)],
)
async def list_nba_games(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    game_date: Annotated[dt.date, Query(alias="date")],
    sync: Annotated[bool, Query(description="Sincroniza scoreboard del día desde NBA")] = False,
    include_predictions: Annotated[bool, Query()] = True,
) -> NbaGamesListResponse:
    if sync:
        try:
            client = NbaApiClient()
            await sync_games_for_date(session, client, game_date.isoformat())
            await session.commit()
        except Exception:
            log.warning("nba scoreboard sync failed date=%s", game_date, exc_info=True)
            await session.rollback()

    rows = (
        (
            await session.execute(
                select(NbaGame)
                .where(NbaGame.game_date == game_date)
                .options(selectinload(NbaGame.home_team), selectinload(NbaGame.away_team))
                .order_by(NbaGame.game_id)
            )
        )
        .scalars()
        .all()
    )

    if rows:
        try:
            await evaluate_nba_predictions_for_final_games(session, rows)
            await session.commit()
        except Exception:
            log.warning("nba evaluate predictions failed", exc_info=True)

    snap_by_id: dict[str, NbaGameFeatureSnapshot] = {}
    meta_info: list[str] = []
    missing = 0
    if include_predictions and rows:
        ids = [g.game_id for g in rows]
        snaps = (
            (
                await session.execute(
                    select(NbaGameFeatureSnapshot).where(NbaGameFeatureSnapshot.game_id.in_(ids))
                )
            )
            .scalars()
            .all()
        )
        snap_by_id = {s.game_id: s for s in snaps}
        missing = sum(1 for g in rows if g.game_id not in snap_by_id)
        if get_nba_prediction_service_optional(request) is None:
            meta_info.append(
                "Modelo NBA no cargado: entrena con "
                "`python -m app.ml.train_nba_from_db` y reinicia."
            )

    out: list[NbaGameDetailResponse] = []
    for g in rows:
        pred: NbaPredictionResponse | None = None
        if include_predictions:
            pred = await _compute_or_cache_prediction(
                request, session, g, snap_by_id.get(g.game_id), "list_nba_games"
            )
        out.append(_game_detail(g, pred, include_payload=False))
    return NbaGamesListResponse(
        games=out,
        meta=NbaGamesListMeta(info=meta_info, missing_snapshot_count=missing),
    )


@router.get(
    "/nba/games/{game_id}",
    response_model=NbaGameDetailResponse,
    dependencies=[Depends(rate_limit_public_read)],
)
async def get_nba_game(
    request: Request,
    game_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    include_predictions: Annotated[bool, Query()] = True,
) -> NbaGameDetailResponse:
    game = (
        await session.execute(
            select(NbaGame)
            .where(NbaGame.game_id == game_id)
            .options(selectinload(NbaGame.home_team), selectinload(NbaGame.away_team))
        )
    ).scalar_one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    pred: NbaPredictionResponse | None = None
    if include_predictions:
        snap = (
            await session.execute(
                select(NbaGameFeatureSnapshot).where(NbaGameFeatureSnapshot.game_id == game_id)
            )
        ).scalar_one_or_none()
        pred = await _compute_or_cache_prediction(request, session, game, snap, "get_nba_game")
    return _game_detail(game, pred)


@router.get(
    "/nba/predict/{game_id}",
    response_model=NbaPredictionResponse,
    dependencies=[Depends(rate_limit_public_read)],
)
async def predict_nba_game(
    game_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    model: NbaModelKind = Query(
        default=DEFAULT_NBA_MODEL,
        description="Modelo: 'xgb' (default), 'lgbm', 'catboost' o 'ensemble'",
    ),
) -> NbaPredictionResponse:
    game = (
        await session.execute(select(NbaGame).where(NbaGame.game_id == game_id))
    ).scalar_one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    svc = get_nba_prediction_service(request, model)
    model_version = svc.model_version
    cached = await get_cached_nba_prediction(session, game_id, model_version)
    if cached is not None:
        return cached
    snap = (
        await session.execute(
            select(NbaGameFeatureSnapshot).where(NbaGameFeatureSnapshot.game_id == game_id)
        )
    ).scalar_one_or_none()
    try:
        result = svc.predict(game_id, snap)
        out = prediction_response_from_result(result)
    except Exception:
        log.exception("nba predict failed game=%s model=%s", game_id, model)
        raise HTTPException(status_code=500, detail="Error al calcular la estimación.") from None
    try:
        await upsert_nba_prediction_cache(session, out, f"api_get_{model}")
    except Exception:
        log.warning("nba prediction cache upsert failed game=%s", game_id, exc_info=True)
    return out


@router.post(
    "/nba/sync-season",
    response_model=dict,
    dependencies=[Depends(rate_limit_public_write)],
)
async def sync_nba_season(
    session: Annotated[AsyncSession, Depends(get_db)],
    season: Annotated[str, Query(description="Temporada, p. ej. 2023-24")],
    season_type: Annotated[str, Query()] = "Regular Season",
) -> dict:
    client = NbaApiClient(season_type=season_type)
    games = await sync_season(session, client, season, season_type=season_type)
    await session.commit()
    return {"season": season, "games_synced": len(games)}
