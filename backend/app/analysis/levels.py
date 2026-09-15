from __future__ import annotations

from typing import Any
import math

import numpy as np
import pandas as pd


# ============================================================
# SUPPORT / RESISTANCE ZONE ENGINE V1.1
# ============================================================
#
# Optimized version of S/R Zone Engine V1.
#
# Detects:
#   - Confirmed swing support
#   - Confirmed swing resistance
#   - Repeated touches
#   - Zone strength
#   - FRESH / TESTED / BROKEN
#   - Breakout
#   - Retest
#   - Distance from current price
#   - ATR-normalized distance
#
# IMPORTANT:
#   - No future candles are used to form a historical swing
#     before its confirmation point.
#   - ATR is precomputed once.
#   - Zone lifecycle uses vectorized NumPy operations.
#   - This is deterministic context analysis, not prediction.
# ============================================================


# ============================================================
# PARAMETERS
# ============================================================

MIN_DATA = 50

ATR_PERIOD = 14

SWING_LEFT = 4
SWING_RIGHT = 4

ZONE_WIDTH_ATR = 0.25

MERGE_DISTANCE_ATR = 0.50

TOUCH_TOLERANCE_ATR = 0.35

BREAK_BUFFER_ATR = 0.20

MAX_ZONE_DISTANCE_ATR = 8.0

MIN_TOUCHES_STRONG = 3

RECENT_ZONE_BARS = 1000


# ============================================================
# BASIC HELPERS
# ============================================================

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:
        x = float(value)

        if not math.isfinite(x):
            return default

        return x

    except Exception:
        return default


def _timestamp(
    df: pd.DataFrame,
    index: int,
):
    if "timestamp" not in df.columns:
        return None

    try:
        return df.iloc[index]["timestamp"]
    except Exception:
        return None


def _price(
    df: pd.DataFrame,
    index: int,
    column: str,
) -> float:

    return _safe_float(
        df.iloc[index][column],
        0.0,
    )


# ============================================================
# ATR PRECOMPUTATION
# ============================================================

def _prepare_atr(
    df: pd.DataFrame,
) -> np.ndarray:

    high = pd.to_numeric(
        df["high"],
        errors="coerce",
    )

    low = pd.to_numeric(
        df["low"],
        errors="coerce",
    )

    close = pd.to_numeric(
        df["close"],
        errors="coerce",
    )

    previous_close = close.shift(1)

    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = (
        true_range
        .rolling(
            ATR_PERIOD,
            min_periods=ATR_PERIOD,
        )
        .mean()
    )

    # Fill initial unavailable ATR values using
    # expanding mean so historical zones still have
    # usable volatility information.
    atr = atr.fillna(
        true_range.expanding(
            min_periods=2
        ).mean()
    )

    atr = atr.fillna(0.0)

    return atr.to_numpy(
        dtype=float
    )


def _atr_value(
    atr_values: np.ndarray,
    index: int,
) -> float:

    if (
        index < 0
        or index >= len(atr_values)
    ):
        return 0.0

    value = _safe_float(
        atr_values[index],
        0.0,
    )

    return value


# ============================================================
# CONFIRMED SWINGS
# ============================================================

def _confirmed_swings(
    df: pd.DataFrame,
) -> list[dict[str, Any]]:

    required = (
        SWING_LEFT
        + SWING_RIGHT
        + 5
    )

    if len(df) < required:
        return []

    highs = pd.to_numeric(
        df["high"],
        errors="coerce",
    ).to_numpy(
        dtype=float
    )

    lows = pd.to_numeric(
        df["low"],
        errors="coerce",
    ).to_numpy(
        dtype=float
    )

    swings = []

    start = SWING_LEFT

    end = (
        len(df)
        - SWING_RIGHT
    )

    for i in range(
        start,
        end,
    ):

        left = i - SWING_LEFT
        right = (
            i
            + SWING_RIGHT
            + 1
        )

        high_window = highs[
            left:right
        ]

        low_window = lows[
            left:right
        ]

        current_high = highs[i]
        current_low = lows[i]

        if (
            np.isfinite(current_high)
            and current_high
            >= np.nanmax(
                high_window
            )
        ):

            swings.append(
                {
                    "index": int(i),
                    "confirmation_index": int(
                        i + SWING_RIGHT
                    ),
                    "timestamp": _timestamp(
                        df,
                        i,
                    ),
                    "kind": "RESISTANCE",
                    "price": float(
                        current_high
                    ),
                }
            )

        if (
            np.isfinite(current_low)
            and current_low
            <= np.nanmin(
                low_window
            )
        ):

            swings.append(
                {
                    "index": int(i),
                    "confirmation_index": int(
                        i + SWING_RIGHT
                    ),
                    "timestamp": _timestamp(
                        df,
                        i,
                    ),
                    "kind": "SUPPORT",
                    "price": float(
                        current_low
                    ),
                }
            )

    swings.sort(
        key=lambda x:
            x["index"]
    )

    return swings


# ============================================================
# ZONE CREATION
# ============================================================

def _new_zone(
    df: pd.DataFrame,
    swing: dict[str, Any],
    atr_values: np.ndarray,
) -> dict[str, Any]:

    idx = swing["index"]

    atr = _atr_value(
        atr_values,
        idx,
    )

    if atr <= 0:
        atr = 1.0

    width = (
        atr
        * ZONE_WIDTH_ATR
    )

    price = swing["price"]

    if swing["kind"] == "RESISTANCE":
        side = "SELL_SIDE"
    else:
        side = "BUY_SIDE"

    return {
        "id": (
            f'{swing["kind"]}_'
            f'{idx}'
        ),

        "kind": swing["kind"],

        "side": side,

        "formation_index": int(
            idx
        ),

        "confirmation_index": int(
            swing["confirmation_index"]
        ),

        "formed_at": swing[
            "timestamp"
        ],

        "center": float(
            price
        ),

        "lower": float(
            price - width
        ),

        "upper": float(
            price + width
        ),

        "touches": 1,

        "strength": 1,

        "state": "FRESH",

        "last_touch_index": int(
            idx
        ),

        "last_touch_timestamp": (
            swing["timestamp"]
        ),

        "breakout": None,

        "retest": None,

        "source": "CONFIRMED_SWING",

        "merged_types": [
            swing["kind"]
        ],
    }


# ============================================================
# MERGE ZONES
# ============================================================

def _merge_zones(
    df: pd.DataFrame,
    swings: list[dict[str, Any]],
    atr_values: np.ndarray,
) -> list[dict[str, Any]]:

    zones = []

    for swing in swings:

        zone = _new_zone(
            df,
            swing,
            atr_values,
        )

        merged = False

        atr = _atr_value(
            atr_values,
            swing["index"],
        )

        if atr <= 0:
            continue

        merge_distance = (
            atr
            * MERGE_DISTANCE_ATR
        )

        for existing in zones:

            if (
                existing["kind"]
                != zone["kind"]
            ):
                continue

            distance = abs(
                existing["center"]
                - zone["center"]
            )

            if distance <= merge_distance:

                old_touches = int(
                    existing["touches"]
                )

                new_touches = int(
                    zone["touches"]
                )

                total = (
                    old_touches
                    + new_touches
                )

                existing["center"] = (
                    existing["center"]
                    * old_touches
                    + zone["center"]
                    * new_touches
                ) / total

                width = (
                    atr
                    * ZONE_WIDTH_ATR
                )

                existing["lower"] = (
                    existing["center"]
                    - width
                )

                existing["upper"] = (
                    existing["center"]
                    + width
                )

                existing["touches"] = (
                    total
                )

                existing["strength"] = (
                    total
                )

                existing[
                    "last_touch_index"
                ] = max(
                    existing[
                        "last_touch_index"
                    ],
                    zone[
                        "last_touch_index"
                    ],
                )

                if (
                    zone["kind"]
                    not in existing[
                        "merged_types"
                    ]
                ):

                    existing[
                        "merged_types"
                    ].append(
                        zone["kind"]
                    )

                merged = True
                break

        if not merged:
            zones.append(
                zone
            )

    return zones


# ============================================================
# ZONE LIFECYCLE - OPTIMIZED
# ============================================================

def _process_zone_lifecycle(
    df: pd.DataFrame,
    zone: dict[str, Any],
    atr_values: np.ndarray,
) -> dict[str, Any]:

    start = max(
        int(
            zone[
                "confirmation_index"
            ]
        ),
        0,
    )

    current_index = (
        len(df) - 1
    )

    if start > current_index:
        return zone

    highs = pd.to_numeric(
        df["high"],
        errors="coerce",
    ).to_numpy(
        dtype=float
    )

    lows = pd.to_numeric(
        df["low"],
        errors="coerce",
    ).to_numpy(
        dtype=float
    )

    closes = pd.to_numeric(
        df["close"],
        errors="coerce",
    ).to_numpy(
        dtype=float
    )

    high = highs[start:]
    low = lows[start:]
    close = closes[start:]
    atr = atr_values[start:]

    valid_atr = atr > 0

    # --------------------------------------------------------
    # Touch detection
    # --------------------------------------------------------

    tolerance = (
        atr
        * TOUCH_TOLERANCE_ATR
    )

    lower = (
        zone["lower"]
        - tolerance
    )

    upper = (
        zone["upper"]
        + tolerance
    )

    interacted = (
        (high >= lower)
        & (low <= upper)
        & valid_atr
    )

    interaction_positions = (
        np.flatnonzero(
            interacted
        )
    )

    if len(
        interaction_positions
    ) > 0:

        absolute_indices = (
            interaction_positions
            + start
        )

        # The formation itself is already counted
        # as the first touch.
        additional_touches = max(
            0,
            len(
                absolute_indices
            ) - 1,
        )

        total_touches = (
            1
            + additional_touches
        )

        last_touch = int(
            absolute_indices[-1]
        )

    else:

        total_touches = 1

        last_touch = int(
            zone[
                "formation_index"
            ]
        )

    # --------------------------------------------------------
    # Breakout detection
    # --------------------------------------------------------

    if zone["kind"] == "RESISTANCE":

        break_level = (
            zone["upper"]
            + atr
            * BREAK_BUFFER_ATR
        )

        broken_mask = (
            (close > break_level)
            & valid_atr
        )

        breakout_direction = (
            "BULLISH"
        )

    else:

        break_level = (
            zone["lower"]
            - atr
            * BREAK_BUFFER_ATR
        )

        broken_mask = (
            (close < break_level)
            & valid_atr
        )

        breakout_direction = (
            "BEARISH"
        )

    breakout_positions = (
        np.flatnonzero(
            broken_mask
        )
    )

    breakout = None

    if len(
        breakout_positions
    ) > 0:

        first_position = int(
            breakout_positions[0]
        )

        breakout_index = (
            start
            + first_position
        )

        breakout_price = _safe_float(
            closes[
                first_position
            ]
        )

        breakout = {
            "index": int(
                breakout_index
            ),
            "timestamp": _timestamp(
                df,
                breakout_index,
            ),
            "direction": (
                breakout_direction
            ),
            "price": float(
                breakout_price
            ),
        }

    # --------------------------------------------------------
    # Retest detection
    # --------------------------------------------------------

    retest = None

    if breakout is not None:

        breakout_index = (
            breakout["index"]
        )

        retest_start = (
            breakout_index
            + 1
        )

        if (
            retest_start
            <= current_index
        ):

            retest_high = highs[
                retest_start:
            ]

            retest_low = lows[
                retest_start:
            ]

            retest_close = closes[
                retest_start:
            ]

            retest_atr = atr_values[
                retest_start:
            ]

            retest_tolerance = (
                retest_atr
                * TOUCH_TOLERANCE_ATR
            )

            touched = (
                (
                    retest_high
                    >= zone["lower"]
                    - retest_tolerance
                )
                &
                (
                    retest_low
                    <= zone["upper"]
                    + retest_tolerance
                )
                &
                (retest_atr > 0)
            )

            positions = np.flatnonzero(
                touched
            )

            if len(positions) > 0:

                if (
                    breakout[
                        "direction"
                    ]
                    == "BULLISH"
                ):

                    valid = (
                        retest_close[
                            positions
                        ]
                        >= zone["upper"]
                    )

                else:

                    valid = (
                        retest_close[
                            positions
                        ]
                        <= zone["lower"]
                    )

                valid_positions = (
                    positions[valid]
                )

                if len(
                    valid_positions
                ) > 0:

                    pos = int(
                        valid_positions[0]
                    )

                    index = (
                        retest_start
                        + pos
                    )

                    retest = {
                        "index": int(
                            index
                        ),
                        "timestamp": (
                            _timestamp(
                                df,
                                index,
                            )
                        ),
                        "direction": (
                            breakout[
                                "direction"
                            ]
                        ),
                        "result": "HOLD",
                    }

    # --------------------------------------------------------
    # State
    # --------------------------------------------------------

    if breakout is not None:
        state = "BROKEN"

    elif total_touches >= 2:
        state = "TESTED"

    else:
        state = "FRESH"

    zone["touches"] = int(
        total_touches
    )

    zone["strength"] = int(
        total_touches
    )

    zone[
        "last_touch_index"
    ] = int(
        last_touch
    )

    zone[
        "last_touch_timestamp"
    ] = _timestamp(
        df,
        last_touch,
    )

    zone["state"] = state

    zone["breakout"] = breakout

    zone["retest"] = retest

    return zone


# ============================================================
# STRENGTH SCORE
# ============================================================

def _zone_strength(
    zone: dict[str, Any],
    current_index: int,
) -> float:

    score = 0.0

    touches = int(
        zone["touches"]
    )

    if touches >= 1:
        score += 25

    if touches >= 2:
        score += 20

    if touches >= 3:
        score += 20

    if touches >= 4:
        score += 10

    if zone["state"] == "TESTED":
        score += 5

    if zone["state"] == "FRESH":
        score += 10

    if zone["state"] == "BROKEN":
        score -= 20

    age = (
        current_index
        - int(
            zone[
                "formation_index"
            ]
        )
    )

    if age <= RECENT_ZONE_BARS:
        score += 10

    elif age <= (
        RECENT_ZONE_BARS * 2
    ):
        score += 5

    return round(
        max(
            0.0,
            min(
                100.0,
                score,
            ),
        ),
        2,
    )


# ============================================================
# MAIN ENGINE
# ============================================================

def analyze_support_resistance(
    df: pd.DataFrame,
) -> dict[str, Any]:

    if df is None or len(df) < MIN_DATA:

        return {
            "status": "INSUFFICIENT_DATA",
            "zones": [],
            "support": [],
            "resistance": [],
            "nearest_support": None,
            "nearest_resistance": None,
        }

    d = df.copy().reset_index(
        drop=True
    )

    current_index = (
        len(d) - 1
    )

    current_price = _price(
        d,
        current_index,
        "close",
    )

    # --------------------------------------------------------
    # Precompute ATR ONCE.
    # This is the major performance optimization.
    # --------------------------------------------------------

    atr_values = _prepare_atr(
        d
    )

    current_atr = _atr_value(
        atr_values,
        current_index,
    )

    if current_atr <= 0:

        return {
            "status": "NO_ATR",
            "zones": [],
            "support": [],
            "resistance": [],
            "nearest_support": None,
            "nearest_resistance": None,
        }

    # --------------------------------------------------------
    # Confirmed swings
    # --------------------------------------------------------

    swings = _confirmed_swings(
        d
    )

    # --------------------------------------------------------
    # Initial zone creation + merging
    # --------------------------------------------------------

    zones = _merge_zones(
        d,
        swings,
        atr_values,
    )

    # --------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------

    processed = []

    for zone in zones:

        if (
            zone[
                "confirmation_index"
            ]
            > current_index
        ):
            continue

        zone = _process_zone_lifecycle(
            d,
            zone,
            atr_values,
        )

        zone[
            "strength_score"
        ] = _zone_strength(
            zone,
            current_index,
        )

        distance = abs(
            zone["center"]
            - current_price
        )

        distance_atr = (
            distance
            / current_atr
        )

        zone[
            "distance_from_price"
        ] = round(
            distance,
            5,
        )

        zone[
            "distance_atr"
        ] = round(
            distance_atr,
            3,
        )

        if (
            zone["center"]
            > current_price
        ):

            zone[
                "position"
            ] = "ABOVE_PRICE"

        elif (
            zone["center"]
            < current_price
        ):

            zone[
                "position"
            ] = "BELOW_PRICE"

        else:

            zone[
                "position"
            ] = "AT_PRICE"

        processed.append(
            zone
        )

    # --------------------------------------------------------
    # Actionable zones
    # --------------------------------------------------------

    actionable = []

    for zone in processed:

        if zone["state"] == "BROKEN":
            continue

        if (
            zone["distance_atr"]
            > MAX_ZONE_DISTANCE_ATR
        ):
            continue

        if (
            zone["kind"]
            == "RESISTANCE"
            and zone["center"]
            > current_price
        ):

            actionable.append(
                zone
            )

        elif (
            zone["kind"]
            == "SUPPORT"
            and zone["center"]
            < current_price
        ):

            actionable.append(
                zone
            )

    # --------------------------------------------------------
    # Separate support/resistance
    # --------------------------------------------------------

    support = sorted(
        [
            zone
            for zone in actionable
            if zone["kind"]
            == "SUPPORT"
        ],
        key=lambda zone:
            zone["distance_atr"],
    )

    resistance = sorted(
        [
            zone
            for zone in actionable
            if zone["kind"]
            == "RESISTANCE"
        ],
        key=lambda zone:
            zone["distance_atr"],
    )

    nearest_support = (
        support[0]
        if support
        else None
    )

    nearest_resistance = (
        resistance[0]
        if resistance
        else None
    )

    # --------------------------------------------------------
    # Context
    # --------------------------------------------------------

    context = {

        "price": current_price,

        "atr": current_atr,

        "nearest_support": (
            nearest_support
        ),

        "nearest_resistance": (
            nearest_resistance
        ),

        "support_count": len(
            support
        ),

        "resistance_count": len(
            resistance
        ),

        "nearest_support_distance_atr": (
            nearest_support[
                "distance_atr"
            ]
            if nearest_support
            else None
        ),

        "nearest_resistance_distance_atr": (
            nearest_resistance[
                "distance_atr"
            ]
            if nearest_resistance
            else None
        ),
    }

    # --------------------------------------------------------
    # Final output
    # --------------------------------------------------------

    return {

        "status": "OK",

        "current_price": (
            current_price
        ),

        "current_atr": (
            current_atr
        ),

        "total_zones": len(
            processed
        ),

        "actionable_zones": len(
            actionable
        ),

        "zones": processed,

        "support": support,

        "resistance": resistance,

        "nearest_support": (
            nearest_support
        ),

        "nearest_resistance": (
            nearest_resistance
        ),

        "context": context,

        "methodology": {

            "engine": (
                "Support Resistance Zone Engine V1.1"
            ),

            "formation": (
                "Confirmed swing based"
            ),

            "zone_width": (
                f"{ZONE_WIDTH_ATR} ATR"
            ),

            "touch_tolerance": (
                f"{TOUCH_TOLERANCE_ATR} ATR"
            ),

            "merge_distance": (
                f"{MERGE_DISTANCE_ATR} ATR"
            ),

            "broken_zone_filter": True,

            "max_actionable_distance_atr": (
                MAX_ZONE_DISTANCE_ATR
            ),

            "atr_precomputed_once": True,

            "lifecycle_vectorized": True,

            "lookahead_on_completed_history": False,

            "prediction": False,

            "score_meaning": (
                "Zone quality/context score, "
                "not win probability"
            ),
        },
    }


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

def support_resistance(
    df: pd.DataFrame,
):

    """
    Backward-compatible interface.

    Existing routes.py can continue calling:

        support_resistance(df)

    The function returns the same simple
    support/resistance list format expected
    by the existing route.
    """

    result = analyze_support_resistance(
        df
    )

    levels = []

    for zone in result.get(
        "support",
        [],
    ):

        levels.append(
            {
                "price": float(
                    zone["center"]
                ),
                "type": "SUPPORT",
                "strength": float(
                    zone[
                        "strength_score"
                    ]
                ),
                "touches": int(
                    zone["touches"]
                ),
                "state": zone[
                    "state"
                ],
            }
        )

    for zone in result.get(
        "resistance",
        [],
    ):

        levels.append(
            {
                "price": float(
                    zone["center"]
                ),
                "type": "RESISTANCE",
                "strength": float(
                    zone[
                        "strength_score"
                    ]
                ),
                "touches": int(
                    zone["touches"]
                ),
                "state": zone[
                    "state"
                ],
            }
        )

    return levels