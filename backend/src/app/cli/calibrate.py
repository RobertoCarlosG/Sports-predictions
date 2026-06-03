"""Standalone calibration script.

Loads evaluated predictions from the database for a given model version,
fits an isotonic regression calibration layer, and saves it to artifacts/.

Usage (from backend/):
  uv run python -m app.cli.calibrate --model-version rf-db-v1
  uv run python -m app.cli.calibrate --model-version xgb-db-v1
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys


async def _async_main(model_version: str) -> None:
    from app.db.session import async_session_factory
    from app.ml.calibration import fit_calibration_from_db, save_calibration

    async with async_session_factory() as session:
        calibrator, n = await fit_calibration_from_db(session, model_version)

    path = save_calibration(model_version, calibrator)
    log = logging.getLogger(__name__)
    log.info("Done. Calibration fitted on %d predictions and saved to %s", n, path)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stdout,
        force=True,
    )
    p = argparse.ArgumentParser(
        description="Fit a probability calibration layer from evaluated predictions in the DB."
    )
    p.add_argument(
        "--model-version",
        default="rf-db-v1",
        help="Base model version string (default: rf-db-v1)",
    )
    args = p.parse_args(argv)
    asyncio.run(_async_main(args.model_version))


if __name__ == "__main__":
    main()
