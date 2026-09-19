
from app.analysis.decision_engine import make_decision


def test_wait_when_confirmation_is_stale():
    result = make_decision(
        mtf={
            "macro_bias": "BEARISH",
            "major_structure": "ALIGNED",
        },
        confluence={},
        entry_confirmation={
            "confirmation": False,
            "status": "WAIT",
            "checks": {
                "bos": {
                    "status": "STALE",
                    "fresh": False,
                },
                "choch": {
                    "status": "STALE",
                    "fresh": False,
                },
                "liquidity": {
                    "status": "STALE",
                    "fresh": False,
                },
                "retest": {
                    "status": "WAIT",
                },
            },
        },
        setup={
            "direction": "SHORT",
            "entry": 4415.05,
            "stop_loss": 4429.22,
            "take_profit_1": 4393.79,
            "rr": 2.0,
        },
        price_action={
            "direction": "NEUTRAL",
            "state": "NEUTRAL",
        },
        min_rr=2.0,
    )

    assert result["decision"] == "WAIT"
    assert result["entry_ready"] is False
    assert "FRESH_STRUCTURE" in result["failed_gates"]

    print("PASS: Stale confirmation correctly returns WAIT")


def test_no_trade_when_macro_is_neutral():
    result = make_decision(
        mtf={
            "macro_bias": "NEUTRAL",
            "major_structure": "ALIGNED",
        },
        confluence={},
        entry_confirmation={},
        setup={},
        price_action={},
        min_rr=2.0,
    )

    assert result["decision"] == "NO_TRADE"
    assert result["entry_ready"] is False

    print("PASS: Neutral macro correctly returns NO_TRADE")


if __name__ == "__main__":
    test_wait_when_confirmation_is_stale()
    test_no_trade_when_macro_is_neutral()
    print("All decision engine tests passed.")