import time
from pathlib import Path

import pandas as pd

from app.services.data import load_csv, timeframe_path
from app.analysis.indicators import add_indicators
from app.analysis.structure import analyze_structure
from app.analysis.liquidity import analyze_liquidity
from app.analysis.levels import support_resistance
from app.analysis.price_action import analyze_price_action


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def timed(name, fn):
    start = time.perf_counter()

    result = fn()

    elapsed = time.perf_counter() - start

    print(
        f"{name:<25} "
        f"{elapsed:8.3f} sec"
    )

    return result


def test_pipeline_speed():

    print("\n===== PIPELINE SPEED TEST =====")

    path = timeframe_path(
        DATA,
        "15m",
        "XAUUSD",
    )

    df = load_csv(
        path,
        limit=5000,
    )

    print(
        "Candles:",
        len(df)
    )

    d = timed(
        "Indicators",
        lambda: add_indicators(df.copy()),
    )

    st = timed(
        "Structure",
        lambda: analyze_structure(d),
    )

    liq = timed(
        "Liquidity",
        lambda: analyze_liquidity(d),
    )

    levels = timed(
        "S/R",
        lambda: support_resistance(d),
    )

    pa = timed(
        "Price Action",
        lambda: analyze_price_action(
            d,
            sr=levels,
            structure=st,
        ),
    )

    print("\n===== RESULTS =====")

    print(
        "Structure:",
        st.get("bias")
    )

    print(
        "Liquidity levels:",
        len(liq.get("levels", []))
        if isinstance(liq, dict)
        else "unknown"
    )

    print(
        "Price Action:",
        pa.get("direction"),
        pa.get("score"),
    )