import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(
    0,
    str(ROOT)
)

from app.analysis.price_action import analyze_price_action


CSV_PATH = (
    ROOT
    / "data"
    / "mt5"
    / "XAUUSD_M15.csv"
)


def test_price_action_engine():

    assert CSV_PATH.exists(), (
        f"XAUUSD M15 data not found: {CSV_PATH}"
    )

    df = pd.read_csv(CSV_PATH)

    result = analyze_price_action(
        df.tail(1000),
        structure={
            "bias": "BULLISH"
        }
    )

    print("\n===== PRICE ACTION ENGINE V1 =====")
    print("STATUS:", result["status"])
    print("DIRECTION:", result["direction"])
    print("SCORE:", result["score"])
    print("ATR:", result["atr"])

    print("\nCURRENT:")
    print(result["current"])

    print("\nEVENTS:")

    for event in result["events"]:
        print(
            f"  {event['type']} | "
            f"{event['direction']} | "
            f"{event['strength']} | "
            f"{event['reason']}"
        )

    print("\nWARNINGS:")
    for warning in result["warnings"]:
        print(" ", warning)

    assert "status" in result
    assert "direction" in result
    assert "score" in result
    assert "events" in result
    assert "warnings" in result

    assert result["direction"] in (
        "BULLISH",
        "BEARISH",
        "NEUTRAL",
    )

    assert 0 <= result["score"] <= 100