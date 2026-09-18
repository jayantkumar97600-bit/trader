import numpy as np
import pandas as pd

from app.analysis.levels import _process_zone_lifecycle


def test_breakout_price_uses_relative_position():
    df = pd.DataFrame({
        "high": [50.0] * 60,
        "low": [49.0] * 60,
        "close": [49.5] * 60,
    })

    # Breakout occurs at absolute index 12.
    df.loc[12, "high"] = 103.0
    df.loc[12, "close"] = 102.0

    atr_values = np.ones(60)

    zone = {
        "kind": "RESISTANCE",
        "confirmation_index": 10,
        "formation_index": 6,
        "lower": 99.0,
        "upper": 101.0,
        "breakout": None,
        "retest": None,
    }

    result = _process_zone_lifecycle(
        df,
        zone,
        atr_values,
    )

    assert result["breakout"]["index"] == 12
    assert result["breakout"]["price"] == 102.0
