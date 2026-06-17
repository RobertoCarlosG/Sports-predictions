"""Tests for app.cli.snapshot_status — argparser and module import."""

from __future__ import annotations

import pytest

from app.cli.snapshot_status import main


def test_cli_help_exits_cleanly() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_cli_unknown_flag_exits_with_error() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--not-a-flag"])
    assert exc.value.code != 0


def test_cli_valid_args_parse_without_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify argparse accepts --season and --show-missing without connecting to DB."""

    async def _noop(**_: object) -> None:
        return None

    monkeypatch.setattr("app.cli.snapshot_status._run", _noop)
    main(["--season", "2025", "--show-missing"])
