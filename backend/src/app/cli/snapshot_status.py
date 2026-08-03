"""Audita el estado de game_feature_snapshots vs games.

Muestra: qué fechas tienen snapshot, cuáles faltan y un resumen por temporada.

Uso:

  python -m app.cli.snapshot_status
  python -m app.cli.snapshot_status --season 2025
  python -m app.cli.snapshot_status --season 2025 --show-missing
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import func, select

from app.db.session import async_session_factory
from app.models.mlb import Game, GameFeatureSnapshot

log = logging.getLogger(__name__)


async def _run(*, season: str | None, show_missing: bool) -> None:
    async with async_session_factory() as session:
        # ── totales por temporada ─────────────────────────────────────────────
        season_q = (
            select(
                Game.season,
                func.count(Game.game_pk).label("total_games"),
                func.count(GameFeatureSnapshot.game_pk).label("with_snapshot"),
                func.min(Game.game_date).label("first_date"),
                func.max(Game.game_date).label("last_date"),
            )
            .outerjoin(GameFeatureSnapshot, GameFeatureSnapshot.game_pk == Game.game_pk)
            .group_by(Game.season)
            .order_by(Game.season)
        )
        if season:
            season_q = season_q.where(Game.season == season)

        rows = (await session.execute(season_q)).all()

        if not rows:
            print("No hay juegos en la base de datos.")
            return

        print()
        print("=" * 66)
        print(f"  {'TEMPORADA':<10} {'JUEGOS':>7} {'SNAPS':>7} {'FALTAN':>7}  " f"{'DESDE':<12} {'HASTA':<12}")
        print("=" * 66)
        for r in rows:
            missing = r.total_games - r.with_snapshot
            flag = "  ←" if missing > 0 else ""
            print(
                f"  {r.season:<10} {r.total_games:>7} {r.with_snapshot:>7} {missing:>7}  "
                f"{str(r.first_date):<12} {str(r.last_date):<12}{flag}"
            )
        print("=" * 66)

        # ── últimas fechas con snapshot ───────────────────────────────────────
        last_snap_q = select(func.max(Game.game_date)).join(
            GameFeatureSnapshot, GameFeatureSnapshot.game_pk == Game.game_pk
        )
        if season:
            last_snap_q = last_snap_q.where(Game.season == season)
        last_snap_date = (await session.execute(last_snap_q)).scalar_one_or_none()

        last_game_q = select(func.max(Game.game_date))
        if season:
            last_game_q = last_game_q.where(Game.season == season)
        last_game_date = (await session.execute(last_game_q)).scalar_one_or_none()

        print()
        print(f"  Último snapshot : {last_snap_date or '—'}")
        print(f"  Último juego    : {last_game_date or '—'}")
        if last_snap_date and last_game_date and last_snap_date < last_game_date:
            gap = (last_game_date - last_snap_date).days
            print(f"  Desfase         : {gap} día(s) sin snapshot")
        print()

        # ── fechas sin snapshot, desglosadas por tipo ────────────────────────
        if show_missing:
            missing_base = (
                select(Game.game_date, Game.season, Game.status, func.count(Game.game_pk).label("n"))
                .outerjoin(GameFeatureSnapshot, GameFeatureSnapshot.game_pk == Game.game_pk)
                .where(GameFeatureSnapshot.game_pk.is_(None))
                .group_by(Game.game_date, Game.season, Game.status)
                .order_by(Game.game_date, Game.season)
            )
            if season:
                missing_base = missing_base.where(Game.season == season)

            all_missing = (await session.execute(missing_base)).all()

            final_missing = [
                r
                for r in all_missing
                if "final" in r.status.lower() or "completed" in r.status.lower() or "game over" in r.status.lower()
            ]
            other_missing = [r for r in all_missing if r not in final_missing]

            if final_missing:
                # Group by date for display
                from itertools import groupby as _groupby

                print(
                    f"  Juegos FINALES sin snapshot — necesitan rebuild "
                    f"({len(set(r.game_date for r in final_missing))} días):"
                )
                for date, grp in _groupby(sorted(final_missing, key=lambda r: r.game_date), key=lambda r: r.game_date):
                    grp_list = list(grp)
                    total = sum(r.n for r in grp_list)
                    statuses = ", ".join(sorted({r.status for r in grp_list}))
                    print(f"    {date}  juegos={total}  ({statuses})")
                print()
            else:
                print("  Sin juegos finales pendientes de snapshot.")
                print()

            if other_missing:
                from itertools import groupby as _groupby

                print(
                    f"  Juegos NO finales sin snapshot — "
                    f"{len(all_missing) - len(final_missing)} registros "
                    f"(no requieren acción inmediata):"
                )
                for date, grp in _groupby(sorted(other_missing, key=lambda r: r.game_date), key=lambda r: r.game_date):
                    grp_list = list(grp)
                    total = sum(r.n for r in grp_list)
                    statuses = ", ".join(sorted({r.status for r in grp_list}))
                    print(f"    {date}  juegos={total}  ({statuses})")
                print()


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Audita el estado de game_feature_snapshots.")
    p.add_argument("--season", default=None, help="Filtrar por temporada (ej. 2025). Default: todas.")
    p.add_argument(
        "--show-missing",
        action="store_true",
        help="Listar fechas con juegos finales que no tienen snapshot.",
    )
    args = p.parse_args(argv)
    asyncio.run(_run(season=args.season, show_missing=args.show_missing))


if __name__ == "__main__":
    main()
