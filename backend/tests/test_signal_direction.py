from app.api.routes import _meets_min_rr, _trade_direction_from_bias


def test_trade_direction_uses_authoritative_macro_bias_values():
    assert _trade_direction_from_bias("BULLISH") == "LONG"
    assert _trade_direction_from_bias("BEARISH") == "SHORT"
    assert _trade_direction_from_bias("NEUTRAL") is None


def test_minimum_rr_tolerates_floating_point_rounding():
    assert _meets_min_rr(1.9999999999999998, 2.0) is True
    assert _meets_min_rr(1.999, 2.0) is False
