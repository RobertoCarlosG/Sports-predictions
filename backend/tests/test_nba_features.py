"""Tests del vector de features NBA (longitud + flag defaults_injected)."""

from __future__ import annotations

from app.ml.nba_features import (
    NBA_FEATURE_NAMES,
    build_nba_feature_matrix_row,
    build_nba_feature_values_for_training,
)
from app.models.nba import NbaGameFeatureSnapshot


def test_feature_names_count():
    assert len(NBA_FEATURE_NAMES) == 18
    assert NBA_FEATURE_NAMES[-1] == "defaults_injected"


def test_no_snapshot_sets_injected_flag():
    row = build_nba_feature_matrix_row(None)
    assert row.shape == (1, 18)
    assert row[0, -1] == 1.0


def test_full_snapshot_does_not_inject():
    snap = NbaGameFeatureSnapshot(
        game_id="x",
        home_win_pct_roll=0.6,
        away_win_pct_roll=0.4,
        home_pts_for_roll=115.0,
        away_pts_for_roll=110.0,
        home_pts_against_roll=108.0,
        away_pts_against_roll=112.0,
        home_net_rating_roll=5.0,
        away_net_rating_roll=-2.0,
        home_pace_roll=100.0,
        away_pace_roll=98.0,
        home_efg_roll=0.55,
        away_efg_roll=0.52,
        home_rest_days=2,
        away_rest_days=1,
        home_is_b2b=0,
        away_is_b2b=1,
    )
    vals = build_nba_feature_values_for_training(snap)
    assert len(vals) == 18
    assert vals[-1] == 0.0  # nada imputado


def test_partial_snapshot_injects_flag():
    snap = NbaGameFeatureSnapshot(game_id="y", home_win_pct_roll=None)
    vals = build_nba_feature_values_for_training(snap)
    assert vals[-1] == 1.0
