from __future__ import annotations

from typing import Any
import math
import pandas as pd


# ============================================================
# LIQUIDITY ENGINE V5.2
# ============================================================

SWING_LEFT = 2
SWING_RIGHT = 2

EQUAL_TOLERANCE_ATR = 0.20
LEVEL_DEDUP_ATR = 0.15

# Only liquidity reasonably close to current market is actionable.
MAX_LEVEL_DISTANCE_ATR = 6.0

# Sweep quality filters
SWEEP_PENETRATION_ATR = 0.75
SWEEP_CLOSE_DISTANCE_ATR = 0.90

# Recent sweep window
RECENT_BARS = 100

# Only keep a limited number of strongest relevant levels.
MAX_ACTIONABLE_LEVELS = 20


# ============================================================
# SAFE HELPERS
# ============================================================

def _safe_float(value):
    try:
        value = float(value)
        if math.isfinite(value):
            return value
    except Exception:
        pass
    return None


def _atr_at(df, index):
    if "atr" in df.columns:
        value = _safe_float(df.iloc[index]["atr"])
        if value and value > 0:
            return value

    start = max(0, index - 14)
    sample = df.iloc[start:index + 1]

    if len(sample) < 2:
        return 0.0

    tr = (sample["high"] - sample["low"]).abs()
    value = _safe_float(tr.mean())

    return value if value and value > 0 else 0.0


def _timestamp(df, index):
    ts = df.iloc[index]["timestamp"]

    if hasattr(ts, "isoformat"):
        return ts.isoformat()

    return str(ts)


# ============================================================
# LIQUIDITY SIDE
# ============================================================

def _level_side(level_type):

    buy_side = {
        "EQH",
        "PDH",
        "PWH",
        "SESSION_HIGH",
    }

    sell_side = {
        "EQL",
        "PDL",
        "PWL",
        "SESSION_LOW",
    }

    if level_type in buy_side:
        return "BUY_SIDE"

    if level_type in sell_side:
        return "SELL_SIDE"

    return "UNKNOWN"


def _position(level_price, current_price):

    if level_price > current_price:
        return "ABOVE_PRICE"

    if level_price < current_price:
        return "BELOW_PRICE"

    return "AT_PRICE"


# ============================================================
# LEVEL CREATION
# ============================================================

def _make_level(
    level_type,
    price,
    formation_index,
    df,
    strength=1.0,
    metadata=None,
):

    return {
        "type": level_type,
        "price": round(float(price), 5),

        "side": _level_side(level_type),

        "formation_index": int(formation_index),
        "formed_at": _timestamp(df, formation_index),

        "strength": round(float(strength), 2),

        "state": "PENDING",

        "sweep_timestamp": None,
        "break_timestamp": None,
        "consumed_timestamp": None,

        "metadata": metadata or {},
    }


# ============================================================
# CONFIRMED SWINGS
# ============================================================

def _confirmed_swings(
    df,
    left=SWING_LEFT,
    right=SWING_RIGHT,
):

    highs = []
    lows = []

    h = df["high"].astype(float).tolist()
    l = df["low"].astype(float).tolist()

    for i in range(left, len(df) - right):

        window_high = h[i - left:i + right + 1]
        window_low = l[i - left:i + right + 1]

        if h[i] == max(window_high):
            highs.append(i)

        if l[i] == min(window_low):
            lows.append(i)

    return highs, lows


# ============================================================
# EQUAL HIGH / LOW
# ============================================================

def _equal_levels(df, swing_highs, swing_lows):

    levels = []

    # ------------------------
    # EQH
    # ------------------------

    for i in range(1, len(swing_highs)):

        a = swing_highs[i - 1]
        b = swing_highs[i]

        atr = _atr_at(df, b)

        if atr <= 0:
            continue

        pa = float(df.iloc[a]["high"])
        pb = float(df.iloc[b]["high"])

        tolerance = atr * EQUAL_TOLERANCE_ATR

        if abs(pa - pb) <= tolerance:

            price = (pa + pb) / 2.0

            # Swing b needs RIGHT bars to be confirmed.
            formation_index = b + SWING_RIGHT

            if formation_index >= len(df):
                continue

            levels.append(
                _make_level(
                    "EQH",
                    price,
                    formation_index,
                    df,
                    2.0,
                    {
                        "swing_indices": [a, b],
                        "tolerance_atr": EQUAL_TOLERANCE_ATR,
                    },
                )
            )

    # ------------------------
    # EQL
    # ------------------------

    for i in range(1, len(swing_lows)):

        a = swing_lows[i - 1]
        b = swing_lows[i]

        atr = _atr_at(df, b)

        if atr <= 0:
            continue

        pa = float(df.iloc[a]["low"])
        pb = float(df.iloc[b]["low"])

        tolerance = atr * EQUAL_TOLERANCE_ATR

        if abs(pa - pb) <= tolerance:

            price = (pa + pb) / 2.0

            formation_index = b + SWING_RIGHT

            if formation_index >= len(df):
                continue

            levels.append(
                _make_level(
                    "EQL",
                    price,
                    formation_index,
                    df,
                    2.0,
                    {
                        "swing_indices": [a, b],
                        "tolerance_atr": EQUAL_TOLERANCE_ATR,
                    },
                )
            )

    return levels


# ============================================================
# PREVIOUS DAY / WEEK LEVELS
# ============================================================

def _period_levels(df):

    d = df.copy()

    ts = pd.to_datetime(d["timestamp"], utc=True)

    d["_date"] = ts.dt.date
    d["_week"] = ts.dt.to_period("W-SUN")

    levels = []

    # ------------------------
    # Previous Day
    # ------------------------

    grouped_days = list(
        d.groupby("_date", sort=True)
    )

    for i in range(1, len(grouped_days)):

        previous_date, previous = grouped_days[i - 1]
        current_date, current = grouped_days[i]

        pdh = float(previous["high"].max())
        pdl = float(previous["low"].min())

        formation_index = int(current.index[0])

        levels.append(
            _make_level(
                "PDH",
                pdh,
                formation_index,
                df,
                2.0,
                {
                    "reference_date": str(previous_date),
                    "target_date": str(current_date),
                },
            )
        )

        levels.append(
            _make_level(
                "PDL",
                pdl,
                formation_index,
                df,
                2.0,
                {
                    "reference_date": str(previous_date),
                    "target_date": str(current_date),
                },
            )
        )

    # ------------------------
    # Previous Week
    # ------------------------

    grouped_weeks = list(
        d.groupby("_week", sort=True)
    )

    for i in range(1, len(grouped_weeks)):

        previous_week, previous = grouped_weeks[i - 1]
        current_week, current = grouped_weeks[i]

        pwh = float(previous["high"].max())
        pwl = float(previous["low"].min())

        formation_index = int(current.index[0])

        levels.append(
            _make_level(
                "PWH",
                pwh,
                formation_index,
                df,
                3.0,
                {
                    "reference_week": str(previous_week),
                    "target_week": str(current_week),
                },
            )
        )

        levels.append(
            _make_level(
                "PWL",
                pwl,
                formation_index,
                df,
                3.0,
                {
                    "reference_week": str(previous_week),
                    "target_week": str(current_week),
                },
            )
        )

    return levels


# ============================================================
# SESSION LEVELS
# ============================================================

def _session_levels(df):

    d = df.copy()

    ts = pd.to_datetime(d["timestamp"], utc=True)

    d["_date"] = ts.dt.date

    levels = []

    grouped = list(
        d.groupby("_date", sort=True)
    )

    # Important:
    # Yesterday's completed session becomes available
    # only when the next session starts.

    for i in range(len(grouped) - 1):

        session_date, session = grouped[i]
        next_date, next_session = grouped[i + 1]

        high = float(session["high"].max())
        low = float(session["low"].min())

        formation_index = int(next_session.index[0])

        levels.append(
            _make_level(
                "SESSION_HIGH",
                high,
                formation_index,
                df,
                1.5,
                {
                    "session_date": str(session_date),
                    "available_from": str(next_date),
                },
            )
        )

        levels.append(
            _make_level(
                "SESSION_LOW",
                low,
                formation_index,
                df,
                1.5,
                {
                    "session_date": str(session_date),
                    "available_from": str(next_date),
                },
            )
        )

    return levels


# ============================================================
# DEDUPLICATION
# ============================================================

def _deduplicate_levels(levels, df):

    result = []

    priority = {
        "PWH": 5,
        "PWL": 5,

        "PDH": 4,
        "PDL": 4,

        "EQH": 3,
        "EQL": 3,

        "SESSION_HIGH": 2,
        "SESSION_LOW": 2,
    }

    levels = sorted(
        levels,
        key=lambda x: (
            priority.get(x["type"], 0),
            x["strength"],
        ),
        reverse=True,
    )

    for level in levels:

        atr = _atr_at(
            df,
            min(
                level["formation_index"],
                len(df) - 1,
            ),
        )

        if atr <= 0:
            continue

        duplicate = False

        for existing in result:

            if existing["side"] != level["side"]:
                continue

            distance = abs(
                existing["price"] - level["price"]
            )

            if distance <= atr * LEVEL_DEDUP_ATR:

                duplicate = True

                existing["strength"] = round(
                    max(
                        existing["strength"],
                        level["strength"],
                    ),
                    2,
                )

                existing.setdefault(
                    "merged_types",
                    [],
                )

                existing["merged_types"].append(
                    level["type"]
                )

                break

        if not duplicate:
            result.append(level)

    return result


# ============================================================
# LEVEL STATE
# ============================================================

def _activate_level(
    level,
    current_index,
    current_price,
):

    if current_index < level["formation_index"]:

        level["state"] = "PENDING"

        return

    if level["state"] == "PENDING":

        level["state"] = "ACTIVE"

    level["position"] = _position(
        level["price"],
        current_price,
    )

    level["bars_since_formation"] = (
        current_index -
        level["formation_index"]
    )


# ============================================================
# SWEEP DETECTION
# ============================================================

def _detect_sweep(
    candle,
    level,
    atr,
):

    if atr <= 0:
        return None

    price = float(level["price"])

    high = float(candle["high"])
    low = float(candle["low"])

    close = float(candle["close"])
    open_price = float(candle["open"])

    side = level["side"]

    # ========================================================
    # BUY-SIDE LIQUIDITY
    #
    # Price trades above EQH/PDH/etc.
    # then closes back below it.
    #
    # => bearish liquidity sweep
    # ========================================================

    if side == "BUY_SIDE":

        if high <= price:
            return None

        penetration = high - price

        if penetration > atr * SWEEP_PENETRATION_ATR:
            return None

        if close >= price:
            return None

        upper_wick = (
            high -
            max(open_price, close)
        )

        rejection = (
            upper_wick >=
            max(
                abs(close - open_price) * 0.5,
                atr * 0.05,
            )
        )

        if not rejection:
            return None

        if abs(close - price) > atr * SWEEP_CLOSE_DISTANCE_ATR:
            return None

        return {
            "direction": "BEARISH",
            "sweep_price": round(high, 5),
            "close_after_sweep": round(close, 5),
            "penetration": round(penetration, 5),
            "rejection": True,
        }

    # ========================================================
    # SELL-SIDE LIQUIDITY
    #
    # Price trades below EQL/PDL/etc.
    # then closes back above it.
    #
    # => bullish liquidity sweep
    # ========================================================

    if side == "SELL_SIDE":

        if low >= price:
            return None

        penetration = price - low

        if penetration > atr * SWEEP_PENETRATION_ATR:
            return None

        if close <= price:
            return None

        lower_wick = (
            min(open_price, close) -
            low
        )

        rejection = (
            lower_wick >=
            max(
                abs(close - open_price) * 0.5,
                atr * 0.05,
            )
        )

        if not rejection:
            return None

        if abs(close - price) > atr * SWEEP_CLOSE_DISTANCE_ATR:
            return None

        return {
            "direction": "BULLISH",
            "sweep_price": round(low, 5),
            "close_after_sweep": round(close, 5),
            "penetration": round(penetration, 5),
            "rejection": True,
        }

    return None


# ============================================================
# CLEAN BREAK DETECTION
# ============================================================

def _detect_break(candle, level):

    price = float(level["price"])

    high = float(candle["high"])
    low = float(candle["low"])
    close = float(candle["close"])

    if level["side"] == "BUY_SIDE":

        if close > price and low > price:

            return {
                "direction": "BULLISH",
                "break_price": round(close, 5),
            }

    if level["side"] == "SELL_SIDE":

        if close < price and high < price:

            return {
                "direction": "BEARISH",
                "break_price": round(close, 5),
            }

    return None


# ============================================================
# TEMPORAL ENGINE
# ============================================================

def _run_temporal_engine(
    df,
    levels,
):

    sweeps = []

    for i in range(len(df)):

        candle = df.iloc[i]

        current_price = float(
            candle["close"]
        )

        atr = _atr_at(df, i)

        for level in levels:

            # ------------------------------------------------
            # NO LOOKAHEAD
            # ------------------------------------------------

            if i < level["formation_index"]:
                continue

            _activate_level(
                level,
                i,
                current_price,
            )

            # ------------------------------------------------
            # CONSUMED
            # ------------------------------------------------

            if level["state"] == "CONSUMED":
                continue

            # ------------------------------------------------
            # SWEPT → wait for subsequent clean break
            # ------------------------------------------------

            if level["state"] == "SWEPT":

                br = _detect_break(
                    candle,
                    level,
                )

                if br:

                    level["state"] = "CONSUMED"

                    level[
                        "consumed_timestamp"
                    ] = _timestamp(df, i)

                continue

            # ------------------------------------------------
            # BROKEN
            # ------------------------------------------------

            if level["state"] == "BROKEN":
                continue

            # ------------------------------------------------
            # ACTIVE
            # ------------------------------------------------

            if level["state"] != "ACTIVE":
                continue

            # ------------------------------------------------
            # SWEEP
            # ------------------------------------------------

            sweep = _detect_sweep(
                candle,
                level,
                atr,
            )

            if sweep:

                level["state"] = "SWEPT"

                level[
                    "sweep_timestamp"
                ] = _timestamp(df, i)

                bars_ago = (
                    len(df) - 1 - i
                )

                sweeps.append(
                    {
                        "level_type": level["type"],
                        "level_price": level["price"],
                        "side": level["side"],

                        "direction": sweep[
                            "direction"
                        ],

                        "index": i,
                        "timestamp": _timestamp(
                            df,
                            i,
                        ),

                        "sweep_price": sweep[
                            "sweep_price"
                        ],

                        "close_after_sweep": sweep[
                            "close_after_sweep"
                        ],

                        "penetration": sweep[
                            "penetration"
                        ],

                        "rejection": sweep[
                            "rejection"
                        ],

                        "bars_ago": bars_ago,

                        "recent": (
                            bars_ago <=
                            RECENT_BARS
                        ),
                    }
                )

                continue

            # ------------------------------------------------
            # CLEAN BREAK
            # ------------------------------------------------

            br = _detect_break(
                candle,
                level,
            )

            if br:

                level["state"] = "BROKEN"

                level[
                    "break_timestamp"
                ] = _timestamp(df, i)

    # ========================================================
    # FINAL STATE
    # ========================================================

    current_price = float(
        df.iloc[-1]["close"]
    )

    current_index = len(df) - 1

    for level in levels:

        if current_index < level[
            "formation_index"
        ]:

            level["state"] = "PENDING"

            continue

        level["position"] = _position(
            level["price"],
            current_price,
        )

        level["bars_since_formation"] = (
            current_index -
            level["formation_index"]
        )

        level["recent"] = (
            level["bars_since_formation"]
            <= RECENT_BARS
        )

    return levels, sweeps


# ============================================================
# V5.2 RELEVANCE FILTER
# ============================================================

def _relevant_active_levels(
    levels,
    current_price,
    current_atr,
):

    if current_atr <= 0:
        return []

    candidates = []

    for level in levels:

        # Only ACTIVE levels.
        if level["state"] != "ACTIVE":
            continue

        distance = abs(
            level["price"] -
            current_price
        )

        distance_atr = (
            distance /
            current_atr
        )

        # ----------------------------------------------------
        # Distance filter
        # ----------------------------------------------------

        if distance_atr > MAX_LEVEL_DISTANCE_ATR:
            continue

        # ----------------------------------------------------
        # Correct-side filter
        #
        # BUY-SIDE must be ABOVE price.
        # SELL-SIDE must be BELOW price.
        # ----------------------------------------------------

        if (
            level["side"] == "BUY_SIDE"
            and level["price"] <= current_price
        ):
            continue

        if (
            level["side"] == "SELL_SIDE"
            and level["price"] >= current_price
        ):
            continue

        level["distance_from_price"] = round(
            distance,
            5,
        )

        level["distance_atr"] = round(
            distance_atr,
            3,
        )

        candidates.append(level)

    # Strongest + nearest first.
    candidates.sort(
        key=lambda x: (
            -x["strength"],
            x["distance_atr"],
        )
    )

    return candidates[:MAX_ACTIONABLE_LEVELS]


# ============================================================
# MAIN ENGINE
# ============================================================

def analyze_liquidity(df):

    if df is None or len(df) < 50:

        return {
            "status": "INSUFFICIENT_DATA",
            "current_price": None,
            "levels": [],
            "actionable": [],
            "sweeps": [],
            "recent_sweeps": [],
            "nearest_buy_side": None,
            "nearest_sell_side": None,
        }

    d = df.copy().reset_index(drop=True)

    if "timestamp" not in d.columns:

        if isinstance(
            d.index,
            pd.DatetimeIndex,
        ):

            d["timestamp"] = d.index

        else:

            raise ValueError(
                "Liquidity engine requires timestamp column."
            )

    d["timestamp"] = pd.to_datetime(
        d["timestamp"],
        utc=True,
    )

    current_price = float(
        d.iloc[-1]["close"]
    )

    current_atr = _atr_at(
        d,
        len(d) - 1,
    )

    # ========================================================
    # DETECT LEVELS
    # ========================================================

    swing_highs, swing_lows = _confirmed_swings(
        d,
        SWING_LEFT,
        SWING_RIGHT,
    )

    levels = _equal_levels(
        d,
        swing_highs,
        swing_lows,
    )

    levels.extend(
        _period_levels(d)
    )

    levels.extend(
        _session_levels(d)
    )

    # ========================================================
    # DEDUP
    # ========================================================

    levels = _deduplicate_levels(
        levels,
        d,
    )

    # ========================================================
    # TEMPORAL STATE MACHINE
    # ========================================================

    levels, sweeps = _run_temporal_engine(
        d,
        levels,
    )

    # ========================================================
    # ONLY RELEVANT ACTIVE LEVELS
    # ========================================================

    actionable = _relevant_active_levels(
        levels,
        current_price,
        current_atr,
    )

    # ========================================================
    # NEAREST LIQUIDITY
    # ========================================================

    buy_levels = [
        x
        for x in actionable
        if (
            x["side"] == "BUY_SIDE"
            and x["price"] > current_price
        )
    ]

    sell_levels = [
        x
        for x in actionable
        if (
            x["side"] == "SELL_SIDE"
            and x["price"] < current_price
        )
    ]

    nearest_buy = (
        min(
            buy_levels,
            key=lambda x:
            x["price"] - current_price,
        )
        if buy_levels
        else None
    )

    nearest_sell = (
        min(
            sell_levels,
            key=lambda x:
            current_price - x["price"],
        )
        if sell_levels
        else None
    )

    # ========================================================
    # RECENT SWEEPS
    # ========================================================

    recent_sweeps = [
        x
        for x in sweeps
        if x.get("recent") is True
    ]

    recent_sweeps.sort(
        key=lambda x:
        x["index"],
        reverse=True,
    )

    # ========================================================
    # STATE COUNTS
    # ========================================================

    state_counts = {}

    for level in levels:

        state = level["state"]

        state_counts[state] = (
            state_counts.get(state, 0) + 1
        )

    # ========================================================
    # SIDE COUNTS
    # ========================================================

    side_counts = {
        "BUY_SIDE": sum(
            x["side"] == "BUY_SIDE"
            for x in levels
        ),

        "SELL_SIDE": sum(
            x["side"] == "SELL_SIDE"
            for x in levels
        ),
    }

    # ========================================================
    # RESULT
    # ========================================================

    return {

        "status": "OK",

        "current_price": round(
            current_price,
            5,
        ),

        "current_atr": round(
            current_atr,
            5,
        ),

        "total_levels": len(levels),

        "actionable_levels": len(
            actionable
        ),

        "buy_side_levels": (
            side_counts["BUY_SIDE"]
        ),

        "sell_side_levels": (
            side_counts["SELL_SIDE"]
        ),

        "state_counts": state_counts,

        "nearest_buy_side": nearest_buy,

        "nearest_sell_side": nearest_sell,

        "sweeps": sweeps,

        "recent_sweeps": recent_sweeps,

        "sweep_count": len(sweeps),

        "recent_sweep_count": len(
            recent_sweeps
        ),

        "levels": levels,

        "actionable": actionable,

        "swing_high_count": len(
            swing_highs
        ),

        "swing_low_count": len(
            swing_lows
        ),

        "methodology": {

            "engine":
                "Temporal Liquidity Engine V5.2",

            "buy_side":
                "EQH, PDH, PWH, SESSION_HIGH",

            "sell_side":
                "EQL, PDL, PWL, SESSION_LOW",

            "level_lifecycle":
                "PENDING → ACTIVE → SWEPT/BROKEN → CONSUMED",

            "sweep_definition":
                "Liquidity penetration + close back through level + rejection",

            "lookahead_protection":
                "Confirmed swings require right-side confirmation bars; historical levels become available only after formation.",

            "relevance_filter":
                "Only ACTIVE liquidity within the configured ATR distance and on the correct side of current price is actionable.",

            "max_actionable_distance_atr":
                MAX_LEVEL_DISTANCE_ATR,

            "max_actionable_levels":
                MAX_ACTIONABLE_LEVELS,

            "prediction":
                "None",

            "score_meaning":
                "Liquidity evidence only; not win probability.",
        },
    }