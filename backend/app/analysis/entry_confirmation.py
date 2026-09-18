from typing import Any


BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

# 5M candles. A confirmation older than this is stale.
MAX_EVENT_AGE_BARS = 12

# Liquidity can remain relevant slightly longer than a
# direct entry event, but it still cannot remain valid forever.
MAX_LIQUIDITY_AGE_BARS = 24

# Minimum displacement required for a fresh structural event.
MIN_BOS_DISPLACEMENT_ATR = 0.75
MIN_CHOCH_DISPLACEMENT_ATR = 0.75


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _safe_float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=None):
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _direction_from_trade(trade_direction):
    if trade_direction in ("LONG", BULLISH):
        return BULLISH

    if trade_direction in ("SHORT", BEARISH):
        return BEARISH

    return NEUTRAL


# ---------------------------------------------------------
# Event freshness
# ---------------------------------------------------------

def _event_age_bars(event, current_index):
    """
    Calculate event age using dataframe index positions.

    This is safer than relying only on timestamps because
    different market sessions can have gaps.
    """

    if not event:
        return None

    event_index = _safe_int(
        event.get("index"),
        None,
    )

    if event_index is None or current_index is None:
        return None

    age = current_index - event_index

    if age < 0:
        return None

    return age


def _classify_event_age(
    age_bars,
    max_age_bars=MAX_EVENT_AGE_BARS,
):
    if age_bars is None:
        return "UNKNOWN"

    if age_bars <= max_age_bars:
        return "FRESH"

    return "STALE"


def _event_quality(
    event,
    current_index,
    max_age_bars,
    min_displacement,
):
    if not event:
        return {
            "status": "WAIT",
            "fresh": False,
            "age_bars": None,
            "reason": "Event unavailable.",
        }

    age_bars = _event_age_bars(
        event,
        current_index,
    )

    age_state = _classify_event_age(
        age_bars,
        max_age_bars,
    )

    displacement = _safe_float(
        event.get("displacement_atr"),
        0,
    )

    if age_state == "UNKNOWN":
        return {
            "status": "WAIT",
            "fresh": False,
            "age_bars": None,
            "displacement_atr": displacement,
            "reason": "Event age cannot be verified.",
        }

    if age_state == "STALE":
        return {
            "status": "STALE",
            "fresh": False,
            "age_bars": age_bars,
            "displacement_atr": displacement,
            "reason": (
                f"Event is {age_bars} candles old; "
                f"maximum allowed is {max_age_bars}."
            ),
        }

    if displacement < min_displacement:
        return {
            "status": "WEAK",
            "fresh": True,
            "age_bars": age_bars,
            "displacement_atr": displacement,
            "reason": (
                f"Event is fresh but displacement "
                f"{displacement:.3f} ATR is below "
                f"{min_displacement:.2f} ATR."
            ),
        }

    return {
        "status": "PASS",
        "fresh": True,
        "age_bars": age_bars,
        "displacement_atr": displacement,
        "reason": "Fresh structural event with sufficient displacement.",
    }


# ---------------------------------------------------------
# Structure
# ---------------------------------------------------------

def _check_structure(
    structure,
    direction,
):
    if not structure:
        return {
            "status": "WAIT",
            "reason": "5M structure unavailable.",
        }

    bias = structure.get(
        "bias",
        NEUTRAL,
    )

    if bias != direction:
        return {
            "status": "WAIT",
            "reason": (
                f"5M structure is {bias}; "
                f"expected {direction}."
            ),
        }

    return {
        "status": "PASS",
        "reason": (
            "5M structure agrees with trade direction."
        ),
    }


# ---------------------------------------------------------
# Fresh BOS
# ---------------------------------------------------------

def _check_bos(
    structure,
    direction,
    current_index,
):
    if not structure:
        return {
            "status": "WAIT",
            "fresh": False,
            "reason": "5M structure unavailable.",
        }

    bos = structure.get("bos", [])

    if not bos:
        return {
            "status": "WAIT",
            "fresh": False,
            "reason": "No confirmed 5M BOS.",
        }

    latest = bos[-1]

    if latest.get("direction") != direction:
        return {
            "status": "WAIT",
            "fresh": False,
            "event": latest,
            "reason": (
                "Latest 5M BOS does not confirm direction."
            ),
        }

    quality = _event_quality(
        latest,
        current_index,
        MAX_EVENT_AGE_BARS,
        MIN_BOS_DISPLACEMENT_ATR,
    )

    quality["event"] = latest

    if quality["status"] == "PASS":
        quality["reason"] = (
            "Fresh 5M BOS confirms direction."
        )

    return quality


# ---------------------------------------------------------
# Fresh CHoCH
# ---------------------------------------------------------

def _check_choch(
    structure,
    direction,
    current_index,
):
    if not structure:
        return {
            "status": "WAIT",
            "fresh": False,
            "reason": "5M structure unavailable.",
        }

    choch = structure.get("choch", [])

    if not choch:
        return {
            "status": "WAIT",
            "fresh": False,
            "reason": "No confirmed 5M CHoCH.",
        }

    latest = choch[-1]

    if latest.get("direction") != direction:
        return {
            "status": "WAIT",
            "fresh": False,
            "event": latest,
            "reason": (
                "Latest 5M CHoCH does not confirm direction."
            ),
        }

    quality = _event_quality(
        latest,
        current_index,
        MAX_EVENT_AGE_BARS,
        MIN_CHOCH_DISPLACEMENT_ATR,
    )

    quality["event"] = latest

    if quality["status"] == "PASS":
        quality["reason"] = (
            "Fresh 5M CHoCH confirms direction."
        )

    return quality


# ---------------------------------------------------------
# Price Action
# ---------------------------------------------------------

def _check_price_action(
    price_action,
    direction,
):
    if not price_action:
        return {
            "status": "WAIT",
            "reason": "5M price action unavailable.",
        }

    pa_direction = price_action.get(
        "direction",
        NEUTRAL,
    )
    expected_pa_direction = _direction_from_trade(direction)

    print(
        "DEBUG PA:",
        "trade_direction=", direction,
        "pa_direction=", pa_direction,
        "expected=", expected_pa_direction,
    )

    pa_state = price_action.get(
        "state",
        "UNKNOWN",
    )

    pa_score = _safe_float(
        price_action.get("score"),
        0.0,
    )

    if pa_direction != expected_pa_direction:
        return {
            "status": "WAIT",
            "reason": (
                "5M price action does not confirm "
                "trade direction."
            ),
        }

    if pa_state != "CONFIRMING":
        return {
            "status": "WAIT",
            "reason": (
                f"5M price action state is "
                f"{pa_state}; confirmation required."
            ),
        }

    if pa_score < 40:
        return {
            "status": "WAIT",
            "reason": (
                f"5M price action score "
                f"{pa_score:.1f} is below minimum 40."
            ),
        }

    return {
        "status": "PASS",
        "reason": (
            "5M price action confirms direction "
            "with valid state and score."
        ),
    }

# ---------------------------------------------------------
# Liquidity
# ---------------------------------------------------------

def _check_liquidity(
    liquidity,
    direction,
    current_index,
):
    if not liquidity:
        return {
            "status": "WAIT",
            "fresh": False,
            "reason": "Liquidity data unavailable.",
        }

    sweeps = liquidity.get(
        "sweeps",
        [],
    )

    if not sweeps:
        return {
            "status": "WAIT",
            "fresh": False,
            "reason": "No confirmed liquidity sweep.",
        }

    latest = sweeps[-1]

    sweep_direction = latest.get(
        "direction",
        NEUTRAL,
    )

    age_bars = _safe_int(
        latest.get("bars_ago"),
        None,
    )

    if age_bars is None:
        age_bars = _event_age_bars(
            latest,
            current_index,
        )
    if age_bars is None:
        return {
            "status": "WAIT",
            "fresh": False,
            "event": latest,
            "reason": (
                "Liquidity sweep age cannot be verified."
            ),
        }

    if age_bars > MAX_LIQUIDITY_AGE_BARS:
        return {
            "status": "STALE",
            "fresh": False,
            "age_bars": age_bars,
            "event": latest,
            "reason": (
                f"Liquidity sweep is {age_bars} candles old; "
                f"maximum allowed is "
                f"{MAX_LIQUIDITY_AGE_BARS}."
            ),
        }

    if sweep_direction != direction:
        return {
            "status": "CONFLICTING",
            "fresh": True,
            "age_bars": age_bars,
            "event": latest,
            "reason": (
                "Fresh liquidity sweep conflicts "
                "with trade direction."
            ),
        }

    return {
        "status": "PASS",
        "fresh": True,
        "age_bars": age_bars,
        "event": latest,
        "reason": (
            "Fresh liquidity sweep confirms direction."
        ),
    }


# ---------------------------------------------------------
# Retest
# ---------------------------------------------------------

def _check_retest(
    df,
    direction,
    structure,
):
    if df is None or len(df) < 5:
        return {
            "status": "WAIT",
            "reason": (
                "Insufficient candles for retest."
            ),
        }

    last = df.iloc[-1]

    close = _safe_float(
        last.get("close")
    )

    high = _safe_float(
        last.get("high")
    )

    low = _safe_float(
        last.get("low")
    )

    if (
        close is None
        or high is None
        or low is None
    ):
        return {
            "status": "WAIT",
            "reason": (
                "Current candle data unavailable."
            ),
        }

    protected_high = None
    protected_low = None

    if structure:
        protected_high_obj = structure.get(
            "protected_high"
        )

        protected_low_obj = structure.get(
            "protected_low"
        )

        if protected_high_obj:
            protected_high = _safe_float(
                protected_high_obj.get("price")
            )

        if protected_low_obj:
            protected_low = _safe_float(
                protected_low_obj.get("price")
            )

    if direction == BEARISH:

        if protected_high is None:
            return {
                "status": "WAIT",
                "reason": (
                    "No valid bearish protected high "
                    "available for retest."
                ),
            }

        if (
            high >= protected_high
            and close < protected_high
        ):
            return {
                "status": "PASS",
                "reason": (
                    "Price retested bearish protected "
                    "high and closed below it."
                ),
                "level": protected_high,
            }

    if direction == BULLISH:

        if protected_low is None:
            return {
                "status": "WAIT",
                "reason": (
                    "No valid bullish protected low "
                    "available for retest."
                ),
            }

        if (
            low <= protected_low
            and close > protected_low
        ):
            return {
                "status": "PASS",
                "reason": (
                    "Price retested bullish protected "
                    "low and closed above it."
                ),
                "level": protected_low,
            }

    return {
        "status": "WAIT",
        "reason": (
            "No confirmed directional retest."
        ),
    }


# ---------------------------------------------------------
# Main Engine
# ---------------------------------------------------------

def analyze_entry_confirmation(
    df,
    mtf: dict[str, Any] | None,
    structure: dict[str, Any] | None,
    liquidity: dict[str, Any] | None,
    price_action: dict[str, Any] | None,
):
    """
    Entry Confirmation V1.1

    Freshness-aware deterministic confirmation engine.

    Important:
    - Old BOS/CHoCH cannot confirm a current entry.
    - Old liquidity cannot confirm a current entry.
    - Missing evidence = WAIT.
    - Conflicting fresh evidence blocks confirmation.
    - No prediction.
    """

    if not mtf:
        return {
            "status": "NO TRADE",
            "direction": None,
            "score": 0,
            "confirmation": False,
            "reason": (
                "MTF analysis unavailable."
            ),
        }

    macro_bias = mtf.get(
        "macro_bias",
        NEUTRAL,
    )

    if macro_bias not in (
        BULLISH,
        BEARISH,
    ):
        return {
            "status": "NO TRADE",
            "direction": None,
            "score": 0,
            "confirmation": False,
            "reason": (
                "No directional macro bias."
            ),
        }

    direction = macro_bias

    current_index = len(df) - 1 if df is not None else None

    checks = {}

    # -----------------------------------------------------
    # Structure
    # -----------------------------------------------------

    checks["structure"] = _check_structure(
        structure,
        direction,
    )

    # -----------------------------------------------------
    # Fresh BOS
    # -----------------------------------------------------

    checks["bos"] = _check_bos(
        structure,
        direction,
        current_index,
    )

    # -----------------------------------------------------
    # Fresh CHoCH
    # -----------------------------------------------------

    checks["choch"] = _check_choch(
        structure,
        direction,
        current_index,
    )

    # -----------------------------------------------------
    # Price Action
    # -----------------------------------------------------

    checks["price_action"] = _check_price_action(
        price_action,
        direction,
    )

    # -----------------------------------------------------
    # Fresh Liquidity
    # -----------------------------------------------------

    checks["liquidity"] = _check_liquidity(
        liquidity,
        direction,
        current_index,
    )

    # -----------------------------------------------------
    # Retest
    # -----------------------------------------------------

    checks["retest"] = _check_retest(
        df,
        direction,
        structure,
    )

    # -----------------------------------------------------
    # Evidence
    # -----------------------------------------------------

    passed = sum(
        1
        for check in checks.values()
        if check.get("status") == "PASS"
    )

    total = len(checks)

    score = (
        round(
            (passed / total) * 100,
            2,
        )
        if total
        else 0
    )

    # -----------------------------------------------------
    # Fresh structural event
    # -----------------------------------------------------

    fresh_bos = (
        checks["bos"].get("status") == "PASS"
    )

    fresh_choch = (
        checks["choch"].get("status") == "PASS"
    )

    structural_event = (
        fresh_bos
        or fresh_choch
    )

    # -----------------------------------------------------
    # Confirmation logic
    # -----------------------------------------------------

    structure_pass = (
        checks["structure"].get("status")
        == "PASS"
    )

    pa_pass = (
        checks["price_action"].get("status")
        == "PASS"
    )

    liquidity_pass = (
        checks["liquidity"].get("status")
        == "PASS"
    )

    liquidity_conflict = (
        checks["liquidity"].get("status")
        == "CONFLICTING"
    )

    retest_pass = (
        checks["retest"].get("status")
        == "PASS"
    )

    # Entry confirmation requires a CURRENT
    # structural event + price action.
    #
    # Liquidity OR retest provides context.
    #
    # A fresh conflicting liquidity sweep blocks entry.

    confirmed = (
        structure_pass
        and structural_event
        and pa_pass
        and (
            liquidity_pass
            or retest_pass
        )
        and not liquidity_conflict
    )

    if confirmed:
        status = "CONFIRMED"

        reason = (
            "Fresh 5M structural confirmation, "
            "price action and contextual confirmation "
            "are aligned."
        )

    elif liquidity_conflict:
        status = "WAIT"

        reason = (
            "Fresh liquidity evidence conflicts "
            "with the directional setup."
        )

    elif passed >= 3:
        status = "PARTIAL"

        reason = (
            "Some confirmation evidence exists, "
            "but current entry requirements are incomplete."
        )

    else:
        status = "WAIT"

        reason = (
            "No sufficiently fresh 5M entry confirmation."
        )

    # -----------------------------------------------------
    # Final result
    # -----------------------------------------------------

    return {
        "status": status,

        "direction": (
            "LONG"
            if direction == BULLISH
            else "SHORT"
        ),

        "score": score,

        "confirmation": confirmed,

        "passed": passed,
        "required_checks": total,

        "checks": checks,

        "freshness": {
            "max_event_age_bars": MAX_EVENT_AGE_BARS,
            "max_liquidity_age_bars": (
                MAX_LIQUIDITY_AGE_BARS
            ),
            "min_bos_displacement_atr": (
                MIN_BOS_DISPLACEMENT_ATR
            ),
            "min_choch_displacement_atr": (
                MIN_CHOCH_DISPLACEMENT_ATR
            ),
        },

        "reason": reason,

        "methodology": {
            "type": (
                "Freshness-aware deterministic "
                "5M entry confirmation"
            ),

            "direction_source": (
                "4H macro bias"
            ),

            "confirmation_source": [
                "5M structure",
                "Fresh BOS/CHoCH",
                "Price Action",
                "Fresh Liquidity",
                "Retest",
            ],

            "stale_events": (
                "Cannot confirm current entry."
            ),

            "prediction": "None",

            "win_probability": (
                "Not calculated"
            ),
        },
    }