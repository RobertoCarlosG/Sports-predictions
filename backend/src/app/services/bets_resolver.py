"""Resolución de resultado de apuestas (BD local → MLB linescore)."""

from __future__ import annotations

import logging
from typing import Any, Literal

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bets import Bet
from app.models.mlb import Game
from app.services.backtest import actual_winner_from_scores, is_final_game_status
from app.services.mlb_client import MlbApiClient, scores_from_linescore_payload

log = logging.getLogger(__name__)

BetStatus = Literal["pending", "won", "lost", "push", "cancelled"]
ResultSource = Literal["local", "mlb_api"]


def _is_final_from_linescore(payload: dict[str, Any]) -> bool:
    gd = payload.get("gameData") or {}
    st = gd.get("status") or {}
    abs_state = str(st.get("abstractGameState") or "")
    detailed = str(st.get("detailedState") or "")
    return is_final_game_status(abs_state) or is_final_game_status(detailed)


async def fetch_scores_for_game(
    session: AsyncSession,
    client: httpx.AsyncClient,
    game_pk: int,
) -> tuple[int | None, int | None, ResultSource | None]:
    """Devuelve (home_score, away_score, source) o (None, None, None) si aún no hay marcador."""
    from sqlalchemy import select

    row = await session.execute(select(Game).where(Game.game_pk == game_pk))
    game = row.scalar_one_or_none()
    if game is None:
        return None, None, None

    if (
        game.home_score is not None
        and game.away_score is not None
        and is_final_game_status(game.status)
    ):
        return int(game.home_score), int(game.away_score), "local"

    from app.core.config import settings

    mlb = MlbApiClient(settings.mlb_api_base_url, client)
    try:
        ls = await mlb.linescore(game_pk)
    except Exception:
        log.warning("linescore failed game_pk=%s", game_pk, exc_info=True)
        return None, None, None

    hs, aws = scores_from_linescore_payload(ls)
    if hs is None or aws is None:
        return None, None, None
    if not _is_final_from_linescore(ls) and not is_final_game_status(game.status):
        return None, None, None

    return int(hs), int(aws), "mlb_api"


def resolve_moneyline(bet_side: str, home_score: int, away_score: int) -> BetStatus:
    aw = actual_winner_from_scores(home_score, away_score)
    if aw == "tie":
        return "push"
    if bet_side == aw:
        return "won"
    return "lost"


def resolve_over_under(bet_side: str, home_score: int, away_score: int, line: float) -> BetStatus:
    total = float(home_score + away_score)
    if total > line:
        actual = "over"
    elif total < line:
        actual = "under"
    else:
        return "push"
    if bet_side == actual:
        return "won"
    return "lost"


def compute_bet_outcome(
    bet: Bet,
    home_score: int,
    away_score: int,
) -> BetStatus:
    if bet.bet_type == "moneyline":
        return resolve_moneyline(bet.bet_side, home_score, away_score)
    if bet.bet_type == "over_under":
        if bet.ou_line is None:
            raise ValueError("over_under requiere ou_line")
        return resolve_over_under(bet.bet_side, home_score, away_score, float(bet.ou_line))
    raise ValueError(f"bet_type desconocido: {bet.bet_type}")
