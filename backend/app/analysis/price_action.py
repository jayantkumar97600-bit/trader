from __future__ import annotations

from typing import Any
import math
import pandas as pd


def _num(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def _calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    if len(df) < 2:
        return 0.0

    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")

    previous_close = close.shift(1)

    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = true_range.rolling(period, min_periods=period).mean()

    return _num(
        atr.iloc[-1],
        _num(true_range.tail(period).mean(), 0.0),
    )


def _candle(row: pd.Series) -> dict[str, float]:
    open_price = _num(row["open"])
    high = _num(row["high"])
    low = _num(row["low"])
    close = _num(row["close"])

    candle_range = max(high - low, 0.0)
    body = abs(close - open_price)

    upper_wick = max(high - max(open_price, close), 0.0)
    lower_wick = max(min(open_price, close) - low, 0.0)

    return {
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "range": candle_range,
        "body": body,
        "body_ratio": body / candle_range if candle_range else 0.0,
        "upper_wick": upper_wick,
        "lower_wick": lower_wick,
        "close_location": (
            (close - low) / candle_range
            if candle_range
            else 0.5
        ),
    }


def _get_zones(
    sr: Any,
    key: str,
) -> list[dict[str, Any]]:

    if not sr:
        return []

    # New S/R engine may return a dictionary
    # such as {"supports": [...], "resistances": [...]}.
    if isinstance(sr, dict):

        zones = sr.get(key) or []

        return [
            zone
            for zone in zones
            if isinstance(zone, dict)
        ]

    # Existing S/R engine may return a flat list of zones.
    if isinstance(sr, list):

        expected_kind = (
            "SUPPORT"
            if key == "supports"
            else "RESISTANCE"
        )

        result = []

        for zone in sr:

            if not isinstance(zone, dict):
                continue

            kind = str(
                zone.get("kind", "")
            ).upper()

            if kind == expected_kind:
                result.append(zone)

        return result

    return []

def _nearest_zone(
    zones: list[dict[str, Any]],
    price: float,
    above: bool,
):
    candidates = []

    for zone in zones:
        center = _num(zone.get("center"))

        if above and center > price:
            candidates.append(
                (abs(center - price), zone)
            )

        elif not above and center < price:
            candidates.append(
                (abs(center - price), zone)
            )

    candidates.sort(key=lambda item: item[0])

    return candidates[0][1] if candidates else None


def analyze_price_action(
    df: pd.DataFrame,
    sr: dict[str, Any] | None = None,
    structure: dict[str, Any] | None = None,
    lookback: int = 20,
) -> dict[str, Any]:
    """
    Deterministic price-action engine.

    Uses completed candles only.
    Does not use future candles.
    Does not predict price.
    """

    minimum_bars = max(30, lookback + 5)

    if df is None or len(df) < minimum_bars:
        return {
            "status": "INSUFFICIENT_DATA",
            "direction": "NEUTRAL",
            "score": 0.0,
            "events": [],
            "warnings": [
                "Not enough candles for price-action analysis."
            ],
        }

    required_columns = {
        "open",
        "high",
        "low",
        "close",
    }

    missing = required_columns - set(df.columns)

    if missing:
        return {
            "status": "INVALID_DATA",
            "direction": "NEUTRAL",
            "score": 0.0,
            "events": [],
            "warnings": [
                f"Missing columns: {sorted(missing)}"
            ],
        }

    data = df.copy().reset_index(drop=True)

    for column in required_columns:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    data = data.dropna(
        subset=list(required_columns)
    ).reset_index(drop=True)

    if len(data) < minimum_bars:
        return {
            "status": "INSUFFICIENT_DATA",
            "direction": "NEUTRAL",
            "score": 0.0,
            "events": [],
            "warnings": [
                "Not enough valid candles after cleaning."
            ],
        }

    atr = _calculate_atr(data)

    current = _candle(data.iloc[-1])
    previous = _candle(data.iloc[-2])

    ranges = (
        data["high"] - data["low"]
    ).clip(lower=0)

    bodies = (
        data["close"] - data["open"]
    ).abs()

    average_range = _num(
        ranges.iloc[-lookback:].mean()
    )

    average_body = _num(
        bodies.iloc[-lookback:].mean()
    )

    events: list[dict[str, Any]] = []
    warnings: list[str] = []

    bullish_score = 0.0
    bearish_score = 0.0

    def add_event(
        event_type: str,
        direction: str,
        strength: float,
        reason: str,
    ):
        nonlocal bullish_score
        nonlocal bearish_score

        events.append(
            {
                "type": event_type,
                "direction": direction,
                "strength": round(
                    float(strength),
                    2,
                ),
                "reason": reason,
            }
        )

        if direction == "BULLISH":
            bullish_score += strength

        elif direction == "BEARISH":
            bearish_score += strength

    # ---------------------------------------------------------
    # 1. REJECTION
    # ---------------------------------------------------------

    if current["range"] > 0:

        bullish_rejection = (
            current["lower_wick"]
            >= max(
                current["body"] * 1.5,
                current["range"] * 0.45,
            )
            and current["close_location"] >= 0.60
        )

        bearish_rejection = (
            current["upper_wick"]
            >= max(
                current["body"] * 1.5,
                current["range"] * 0.45,
            )
            and current["close_location"] <= 0.40
        )

        if bullish_rejection:
            add_event(
                "REJECTION",
                "BULLISH",
                15,
                "Long lower wick with close in upper part of candle.",
            )

        if bearish_rejection:
            add_event(
                "REJECTION",
                "BEARISH",
                15,
                "Long upper wick with close in lower part of candle.",
            )

    # ---------------------------------------------------------
    # 2. MOMENTUM
    # ---------------------------------------------------------

    if (
        average_range > 0
        and current["range"] >= average_range * 1.5
        and current["body_ratio"] >= 0.65
    ):

        if current["close"] > current["open"]:
            add_event(
                "MOMENTUM",
                "BULLISH",
                15,
                "Large bullish candle relative to recent range.",
            )

        elif current["close"] < current["open"]:
            add_event(
                "MOMENTUM",
                "BEARISH",
                15,
                "Large bearish candle relative to recent range.",
            )

    # ---------------------------------------------------------
    # 3. ENGULFING
    # ---------------------------------------------------------

    bullish_engulfing = (
        current["close"] > current["open"]
        and previous["close"] < previous["open"]
        and current["open"] <= previous["close"]
        and current["close"] >= previous["open"]
    )

    bearish_engulfing = (
        current["close"] < current["open"]
        and previous["close"] > previous["open"]
        and current["open"] >= previous["close"]
        and current["close"] <= previous["open"]
    )

    if bullish_engulfing:
        add_event(
            "ENGULFING",
            "BULLISH",
            10,
            "Current bullish body engulfs previous bearish body.",
        )

    if bearish_engulfing:
        add_event(
            "ENGULFING",
            "BEARISH",
            10,
            "Current bearish body engulfs previous bullish body.",
        )

    # ---------------------------------------------------------
    # 4. RANGE EXPANSION / CONTRACTION
    # ---------------------------------------------------------

    recent_ranges = ranges.iloc[-lookback:]

    if len(recent_ranges) >= 10:

        first_half = _num(
            recent_ranges.iloc[
                : len(recent_ranges) // 2
            ].mean()
        )

        second_half = _num(
            recent_ranges.iloc[
                len(recent_ranges) // 2 :
            ].mean()
        )

        if (
            first_half > 0
            and second_half <= first_half * 0.75
        ):
            events.append(
                {
                    "type": "RANGE_CONTRACTION",
                    "direction": "NEUTRAL",
                    "strength": 8,
                    "reason": "Recent candle ranges are contracting.",
                }
            )

        elif (
            first_half > 0
            and second_half >= first_half * 1.35
        ):

            direction = (
                "BULLISH"
                if current["close"] > current["open"]
                else "BEARISH"
            )

            add_event(
                "RANGE_EXPANSION",
                direction,
                8,
                "Recent candle ranges are expanding.",
            )

    # ---------------------------------------------------------
    # 5. LOCAL RANGE BREAKOUT
    # ---------------------------------------------------------

    prior_high = _num(
        data["high"].iloc[
            -lookback - 1 : -1
        ].max()
    )

    prior_low = _num(
        data["low"].iloc[
            -lookback - 1 : -1
        ].min()
    )

    if current["close"] > prior_high:

        add_event(
            "BREAKOUT",
            "BULLISH",
            18,
            "Completed candle closed above prior range high.",
        )

    elif current["close"] < prior_low:

        add_event(
            "BREAKOUT",
            "BEARISH",
            18,
            "Completed candle closed below prior range low.",
        )

    # ---------------------------------------------------------
    # 6. FALSE BREAKOUT
    # ---------------------------------------------------------

    if (
        previous["high"] > prior_high
        and previous["close"] <= prior_high
        and current["close"] < previous["low"]
    ):

        add_event(
            "FALSE_BREAKOUT",
            "BEARISH",
            18,
            "Previous candle swept range high and next candle confirmed downside.",
        )

    if (
        previous["low"] < prior_low
        and previous["close"] >= prior_low
        and current["close"] > previous["high"]
    ):

        add_event(
            "FALSE_BREAKOUT",
            "BULLISH",
            18,
            "Previous candle swept range low and next candle confirmed upside.",
        )

    # ---------------------------------------------------------
    # 7. SUPPORT / RESISTANCE CONTEXT
    # ---------------------------------------------------------

    resistances = _get_zones(
        sr,
        "resistances",
    )

    supports = _get_zones(
        sr,
        "supports",
    )

    nearest_resistance = _nearest_zone(
        resistances,
        current["close"],
        above=True,
    )

    nearest_support = _nearest_zone(
        supports,
        current["close"],
        above=False,
    )

    breakout_buffer = atr * 0.20

    if nearest_resistance:

        resistance_lower = _num(
            nearest_resistance.get("lower")
        )

        resistance_upper = _num(
            nearest_resistance.get("upper")
        )

        if (
            current["close"]
            > resistance_upper + breakout_buffer
        ):

            add_event(
                "SR_BREAKOUT",
                "BULLISH",
                20,
                "Completed candle closed above resistance zone.",
            )

        elif (
            current["high"] > resistance_upper
            and current["close"] < resistance_lower
        ):

            add_event(
                "SR_REJECTION",
                "BEARISH",
                20,
                "Price traded through resistance and closed below the zone.",
            )

        elif (
            previous["close"] > resistance_upper
            and current["low"] <= resistance_upper
            and current["close"] > resistance_upper
        ):

            add_event(
                "RETEST",
                "BULLISH",
                20,
                "Broken resistance was retested and reclaimed.",
            )

    if nearest_support:

        support_lower = _num(
            nearest_support.get("lower")
        )

        support_upper = _num(
            nearest_support.get("upper")
        )

        if (
            current["close"]
            < support_lower - breakout_buffer
        ):

            add_event(
                "SR_BREAKOUT",
                "BEARISH",
                20,
                "Completed candle closed below support zone.",
            )

        elif (
            current["low"] < support_lower
            and current["close"] > support_upper
        ):

            add_event(
                "SR_REJECTION",
                "BULLISH",
                20,
                "Price traded through support and closed above the zone.",
            )

        elif (
            previous["close"] < support_lower
            and current["high"] >= support_lower
            and current["close"] < support_lower
        ):

            add_event(
                "RETEST",
                "BEARISH",
                20,
                "Broken support was retested and rejected.",
            )

    # ---------------------------------------------------------
    # 8. STRUCTURE ALIGNMENT
    # ---------------------------------------------------------

    structure_bias = (
        structure or {}
    ).get(
        "bias",
        "NEUTRAL",
    )

    price_action_direction = "NEUTRAL"

    if bullish_score > bearish_score:
        price_action_direction = "BULLISH"

    elif bearish_score > bullish_score:
        price_action_direction = "BEARISH"

    if structure_bias in (
        "BULLISH",
        "BEARISH",
    ):

        if price_action_direction == structure_bias:

            add_event(
                "STRUCTURE_ALIGNMENT",
                price_action_direction,
                10,
                "Recent price action agrees with structural bias.",
            )

        elif (
            price_action_direction != "NEUTRAL"
        ):

            warnings.append(
                "Recent price action conflicts with structural bias."
            )

    # ---------------------------------------------------------
    # 9. FINAL RESULT
    # ---------------------------------------------------------

    if bullish_score > bearish_score:

        direction = "BULLISH"
        raw_score = bullish_score - bearish_score

    elif bearish_score > bullish_score:

        direction = "BEARISH"
        raw_score = bearish_score - bullish_score

    else:

        direction = "NEUTRAL"
        raw_score = 0.0

    score = min(
        100.0,
        max(
            0.0,
            raw_score * 2.5,
        ),
    )

    if direction == "NEUTRAL":
        status = "NEUTRAL"

    elif score >= 70:
        status = "STRONG"

    elif score >= 40:
        status = "MODERATE"

    else:
        status = "WEAK"

    return {
        "status": status,
        "direction": direction,
        "score": round(score, 2),
        "atr": round(atr, 6),

        "current": {
            **current,
        },

        "context": {
            "prior_range_high": prior_high,
            "prior_range_low": prior_low,
            "average_range": round(
                average_range,
                6,
            ),
            "average_body": round(
                average_body,
                6,
            ),
            "structure_bias": structure_bias,
            "nearest_support": nearest_support,
            "nearest_resistance": nearest_resistance,
        },

        "events": events[-10:],

        "warnings": warnings,

        "methodology": {
            "type": "Deterministic completed-candle price action",
            "lookahead": False,
            "uses_future_candles": False,
            "score_meaning": (
                "Price-action evidence score, not win probability."
            ),
            "prediction": "None",
        },
    }


def price_action(
    df: pd.DataFrame,
    sr: dict[str, Any] | None = None,
    structure: dict[str, Any] | None = None,
) -> dict[str, Any]:

    return analyze_price_action(
        df,
        sr=sr,
        structure=structure,
    )