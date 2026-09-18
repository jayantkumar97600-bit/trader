from typing import Any


BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value, low=0.0, high=100.0):
    return max(low, min(high, float(value)))


def _body(row):
    return abs(
        _safe_float(row.get("close"))
        - _safe_float(row.get("open"))
    )


def _range(row):
    return (
        _safe_float(row.get("high"))
        - _safe_float(row.get("low"))
    )


def _upper_wick(row):
    high = _safe_float(row.get("high"))
    op = _safe_float(row.get("open"))
    close = _safe_float(row.get("close"))

    return high - max(op, close)


def _lower_wick(row):
    low = _safe_float(row.get("low"))
    op = _safe_float(row.get("open"))
    close = _safe_float(row.get("close"))

    return min(op, close) - low


def _candle_direction(row):
    op = _safe_float(row.get("open"))
    close = _safe_float(row.get("close"))

    if close > op:
        return BULLISH

    if close < op:
        return BEARISH

    return NEUTRAL


def _atr(row):
    value = _safe_float(
        row.get("atr"),
        0.0,
    )

    return value if value > 0 else None


# ---------------------------------------------------------
# Candle quality
# ---------------------------------------------------------

def _candle_quality(row):
    candle_range = _range(row)
    body = _body(row)

    if candle_range <= 0:
        return {
            "quality": "INVALID",
            "body_ratio": 0.0,
            "direction": NEUTRAL,
        }

    body_ratio = body / candle_range

    if body_ratio >= 0.70:
        quality = "STRONG"

    elif body_ratio >= 0.45:
        quality = "NORMAL"

    elif body_ratio >= 0.20:
        quality = "WEAK"

    else:
        quality = "INDECISION"

    return {
        "quality": quality,
        "body_ratio": round(body_ratio, 3),
        "direction": _candle_direction(row),
    }


# ---------------------------------------------------------
# Momentum / displacement
# ---------------------------------------------------------

def _momentum(df):
    if df is None or len(df) < 5:
        return {
            "state": "UNKNOWN",
            "direction": NEUTRAL,
            "displacement_atr": 0.0,
        }

    last = df.iloc[-1]

    candle_range = _range(last)
    atr = _atr(last)

    if atr is None or atr <= 0:
        return {
            "state": "UNKNOWN",
            "direction": NEUTRAL,
            "displacement_atr": 0.0,
        }

    displacement = candle_range / atr
    direction = _candle_direction(last)

    if displacement >= 1.5:
        state = "STRONG"

    elif displacement >= 1.0:
        state = "MODERATE"

    else:
        state = "WEAK"

    return {
        "state": state,
        "direction": direction,
        "displacement_atr": round(
            displacement,
            3,
        ),
    }


# ---------------------------------------------------------
# Rejection
# ---------------------------------------------------------

def _rejection(row):
    candle_range = _range(row)

    if candle_range <= 0:
        return {
            "state": "NONE",
            "direction": NEUTRAL,
        }

    upper = _upper_wick(row)
    lower = _lower_wick(row)
    body = _body(row)

    upper_ratio = upper / candle_range
    lower_ratio = lower / candle_range
    body_ratio = body / candle_range

    # Bearish rejection:
    # large upper wick + relatively small body.
    if (
        upper_ratio >= 0.45
        and upper > body * 1.5
    ):
        return {
            "state": "REJECTION",
            "direction": BEARISH,
            "wick_ratio": round(
                upper_ratio,
                3,
            ),
        }

    # Bullish rejection:
    # large lower wick + relatively small body.
    if (
        lower_ratio >= 0.45
        and lower > body * 1.5
    ):
        return {
            "state": "REJECTION",
            "direction": BULLISH,
            "wick_ratio": round(
                lower_ratio,
                3,
            ),
        }

    return {
        "state": "NONE",
        "direction": NEUTRAL,
        "wick_ratio": 0.0,
    }


# ---------------------------------------------------------
# Engulfing
# ---------------------------------------------------------

def _engulfing(df):
    if df is None or len(df) < 2:
        return {
            "state": "NONE",
            "direction": NEUTRAL,
        }

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    prev_open = _safe_float(prev.get("open"))
    prev_close = _safe_float(prev.get("close"))

    curr_open = _safe_float(curr.get("open"))
    curr_close = _safe_float(curr.get("close"))

    # Bullish engulfing
    if (
        prev_close < prev_open
        and curr_close > curr_open
        and curr_open <= prev_close
        and curr_close >= prev_open
    ):
        return {
            "state": "ENGULFING",
            "direction": BULLISH,
        }

    # Bearish engulfing
    if (
        prev_close > prev_open
        and curr_close < curr_open
        and curr_open >= prev_close
        and curr_close <= prev_open
    ):
        return {
            "state": "ENGULFING",
            "direction": BEARISH,
        }

    return {
        "state": "NONE",
        "direction": NEUTRAL,
    }


# ---------------------------------------------------------
# Breakout / false breakout
# ---------------------------------------------------------

def _breakout(df, lookback=20):
    if df is None or len(df) < lookback + 1:
        return {
            "state": "NONE",
            "direction": NEUTRAL,
            "level": None,
        }

    previous = df.iloc[-lookback - 1:-1]
    last = df.iloc[-1]

    previous_high = _safe_float(
        previous["high"].max()
    )

    previous_low = _safe_float(
        previous["low"].min()
    )

    close = _safe_float(last.get("close"))
    high = _safe_float(last.get("high"))
    low = _safe_float(last.get("low"))

    # Bullish breakout
    if close > previous_high:
        return {
            "state": "BREAKOUT",
            "direction": BULLISH,
            "level": previous_high,
        }

    # Bearish breakout
    if close < previous_low:
        return {
            "state": "BREAKOUT",
            "direction": BEARISH,
            "level": previous_low,
        }

    # False breakout above range
    if (
        high > previous_high
        and close < previous_high
    ):
        return {
            "state": "FALSE_BREAKOUT",
            "direction": BEARISH,
            "level": previous_high,
        }

    # False breakout below range
    if (
        low < previous_low
        and close > previous_low
    ):
        return {
            "state": "FALSE_BREAKOUT",
            "direction": BULLISH,
            "level": previous_low,
        }

    return {
        "state": "NONE",
        "direction": NEUTRAL,
        "level": None,
    }


# ---------------------------------------------------------
# Consolidation
# ---------------------------------------------------------

def _consolidation(df, lookback=12):
    if df is None or len(df) < lookback:
        return {
            "state": "UNKNOWN",
            "range_atr": None,
        }

    window = df.iloc[-lookback:]

    high = _safe_float(
        window["high"].max()
    )

    low = _safe_float(
        window["low"].min()
    )

    last_atr = _atr(df.iloc[-1])

    if last_atr is None or last_atr <= 0:
        return {
            "state": "UNKNOWN",
            "range_atr": None,
        }

    range_atr = (high - low) / last_atr

    if range_atr <= 3.0:
        state = "CONSOLIDATION"
    else:
        state = "EXPANDED"

    return {
        "state": state,
        "range_atr": round(
            range_atr,
            3,
        ),
    }


# ---------------------------------------------------------
# Range expansion / contraction
# ---------------------------------------------------------

def _range_behavior(df):
    if df is None or len(df) < 12:
        return {
            "state": "UNKNOWN",
        }

    recent = df.iloc[-5:]
    previous = df.iloc[-10:-5]

    recent_ranges = (
        recent["high"]
        - recent["low"]
    )

    previous_ranges = (
        previous["high"]
        - previous["low"]
    )

    recent_mean = _safe_float(
        recent_ranges.mean()
    )

    previous_mean = _safe_float(
        previous_ranges.mean()
    )

    if previous_mean <= 0:
        return {
            "state": "UNKNOWN",
        }

    ratio = recent_mean / previous_mean

    if ratio >= 1.30:
        state = "EXPANSION"

    elif ratio <= 0.75:
        state = "CONTRACTION"

    else:
        state = "NORMAL"

    return {
        "state": state,
        "ratio": round(
            ratio,
            3,
        ),
    }


# ---------------------------------------------------------
# Directional context
# ---------------------------------------------------------

def _structure_context(
    structure,
    direction,
):
    if not structure:
        return {
            "state": "UNKNOWN",
            "score": 0,
        }

    structure_bias = structure.get(
        "bias",
        NEUTRAL,
    )

    if structure_bias == direction:
        return {
            "state": "ALIGNED",
            "score": 20,
        }

    if structure_bias == NEUTRAL:
        return {
            "state": "NEUTRAL",
            "score": 0,
        }

    return {
        "state": "CONFLICTING",
        "score": -20,
    }


# ---------------------------------------------------------
# S/R context
# ---------------------------------------------------------

def _sr_context(
    sr,
    direction,
    current_price,
):
    if not sr:
        return {
            "state": "NONE",
            "score": 0,
            "zone": None,
        }

    if isinstance(sr, list):
        zones = sr
    else:
        zones = sr.get(
            "relevant_zones",
            [],
        )

    if not zones:
        return {
            "state": "NONE",
            "score": 0,
            "zone": None,
        }

    preferred = (
        "SUPPORT"
        if direction == BULLISH
        else "RESISTANCE"
    )

    candidates = []

    for zone in zones:
        kind = str(
            zone.get("kind", "")
        ).upper()

        if kind != preferred:
            continue

        price = _safe_float(
            zone.get("price"),
            None,
        )

        if price is None:
            continue

        candidates.append(zone)

    if not candidates:
        return {
            "state": "NONE",
            "score": 0,
            "zone": None,
        }

    candidates.sort(
        key=lambda z: _safe_float(
            z.get("strength"),
            0,
        ),
        reverse=True,
    )

    zone = candidates[0]

    return {
        "state": "ALIGNED",
        "score": 15,
        "zone": zone,
    }


# ---------------------------------------------------------
# Main engine
# ---------------------------------------------------------

def analyze_price_action(
    df,
    sr=None,
    structure=None,
    direction=None,
):
    """
    Price Action Engine V2.

    Detects:
    - candle quality
    - momentum/displacement
    - rejection
    - engulfing
    - breakout
    - false breakout
    - consolidation
    - range expansion/contraction
    - structure context
    - S/R context

    Important:
    Individual candle patterns do NOT automatically
    create a trade signal.
    """

    if df is None or len(df) < 30:
        return {
            "status": "INSUFFICIENT_DATA",
            "direction": NEUTRAL,
            "score": 0,
            "patterns": [],
            "reason": "Insufficient candles.",
        }

    last = df.iloc[-1]

    candle = _candle_quality(last)
    momentum = _momentum(df)
    rejection = _rejection(last)
    engulfing = _engulfing(df)
    breakout = _breakout(df)
    consolidation = _consolidation(df)
    range_behavior = _range_behavior(df)

    # If direction is not explicitly supplied,
    # derive directional evidence from structure.
    if direction not in (
        BULLISH,
        BEARISH,
    ):
        if structure:
            direction = structure.get(
                "bias",
                NEUTRAL,
            )

    if direction not in (
        BULLISH,
        BEARISH,
    ):
        direction = NEUTRAL

    # -----------------------------------------------------
    # Evidence scoring
    # -----------------------------------------------------

    score = 0.0
    evidence = []
    warnings = []

    # Structure
    structure_result = _structure_context(
        structure,
        direction,
    )

    score += structure_result["score"]

    if structure_result["state"] == "ALIGNED":
        evidence.append(
            "Price action is aligned with market structure."
        )

    elif structure_result["state"] == "CONFLICTING":
        warnings.append(
            "Price action is against market structure."
        )

    # Candle quality
    if (
        candle["direction"] == direction
        and candle["quality"] == "STRONG"
    ):
        score += 15

        evidence.append(
            "Current candle has strong directional body."
        )

    # Momentum
    if (
        momentum["direction"] == direction
        and momentum["state"] == "STRONG"
    ):
        score += 20

        evidence.append(
            "Current candle shows strong directional displacement."
        )

    elif (
        momentum["direction"] == direction
        and momentum["state"] == "MODERATE"
    ):
        score += 10

        evidence.append(
            "Current candle shows directional momentum."
        )

    # Rejection
    if rejection["direction"] == direction:
        score += 15

        evidence.append(
            "Current candle shows directional rejection."
        )

    elif (
        rejection["direction"]
        == (
            BEARISH
            if direction == BULLISH
            else BULLISH
        )
    ):
        score -= 10

        warnings.append(
            "Current candle shows rejection against direction."
        )

    # Engulfing
    if engulfing["direction"] == direction:
        score += 15

        evidence.append(
            "Current candle forms a directional engulfing pattern."
        )

    # Breakout
    if breakout["direction"] == direction:

        if breakout["state"] == "BREAKOUT":
            score += 20

            evidence.append(
                "Price has broken the recent range in the "
                "direction of the setup."
            )

        elif breakout["state"] == "FALSE_BREAKOUT":
            score += 15

            evidence.append(
                "False breakout produced directional rejection."
            )

    # Opposing breakout
    elif breakout["direction"] not in (
        NEUTRAL,
        direction,
    ):
        warnings.append(
            "Recent range behaviour conflicts with direction."
        )

    # Consolidation
    if consolidation["state"] == "CONSOLIDATION":
        evidence.append(
            "Market is currently in a relatively compressed range."
        )

    # Range expansion
    if range_behavior["state"] == "EXPANSION":
        evidence.append(
            "Recent range is expanding."
        )

    elif range_behavior["state"] == "CONTRACTION":
        warnings.append(
            "Recent range is contracting."
        )

    # S/R
    current_price = _safe_float(
        last.get("close"),
        None,
    )

    sr_result = _sr_context(
        sr,
        direction,
        current_price,
    )

    score += sr_result["score"]

    if sr_result["state"] == "ALIGNED":
        evidence.append(
            "Price action has directional S/R context."
        )

    # -----------------------------------------------------
    # Normalize score
    # -----------------------------------------------------

    score = _clamp(
        score,
        0,
        100,
    )

    # -----------------------------------------------------
    # Determine directional PA
    # -----------------------------------------------------

    directional_evidence = 0

    for item in (
        momentum,
        rejection,
        engulfing,
        breakout,
    ):
        if item.get("direction") == direction:
            directional_evidence += 1

    if score >= 65 and directional_evidence >= 2:
        final_direction = direction
        state = "CONFIRMING"

    elif score >= 45 and directional_evidence >= 1:
        final_direction = direction
        state = "DEVELOPING"

    else:
        final_direction = NEUTRAL
        state = "NEUTRAL"

    # -----------------------------------------------------
    # Final
    # -----------------------------------------------------

    return {
        "status": "OK",

        "direction": final_direction,

        "score": round(
            score,
            2,
        ),

        "state": state,

        "current_candle": candle,

        "momentum": momentum,

        "rejection": rejection,

        "engulfing": engulfing,

        "breakout": breakout,

        "consolidation": consolidation,

        "range_behavior": range_behavior,

        "structure_context": structure_result,

        "sr_context": sr_result,

        "evidence": evidence,

        "warnings": warnings,

        "methodology": {
            "type": (
                "Context-aware deterministic "
                "price action analysis"
            ),

            "patterns_are_contextual": True,

            "components": [
                "Candle quality",
                "Momentum",
                "Displacement",
                "Rejection",
                "Engulfing",
                "Breakout",
                "False breakout",
                "Consolidation",
                "Range expansion/contraction",
                "Structure context",
                "S/R context",
            ],

            "signal_rule": (
                "Individual candle patterns do not "
                "automatically create a trade."
            ),

            "prediction": "None",

            "win_probability": (
                "Not calculated"
            ),
        },
    }