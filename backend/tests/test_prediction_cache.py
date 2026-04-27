from app.services.prediction_cache import ml_pick_from_home_win_probability


def test_ml_pick_from_home_win_probability() -> None:
    assert ml_pick_from_home_win_probability(0.51) == "home"
    assert ml_pick_from_home_win_probability(0.50) == "away"
    assert ml_pick_from_home_win_probability(0.49) == "away"
