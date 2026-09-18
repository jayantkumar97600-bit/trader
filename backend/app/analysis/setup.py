
from typing import Any, Dict, Optional

from .invalidation import validate_invalidation


BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"

LONG = "LONG"
SHORT = "SHORT"


def _safe_float(value: Any, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _trade_direction(bias: str):
    if bias == BULLISH:
        return LONG
    if bias == BEARISH:
        return SHORT
    return None


def _find_directional_zone(
    levels: Optional[Dict[str, Any]],
    direction: str,
):
    if not levels:
        return None

    zones = levels.get("relevant_zones", [])

    if not isinstance(zones, list):
        return None

    preferred = (
        "SUPPORT"
        if direction == BULLISH
        else "RESISTANCE"
    )

    candidates = []

    for zone in zones:
        if not isinstance(zone, dict):
            continue

        kind = str(zone.get("kind", "")).upper()

        if kind != preferred:
            continue

        price = _safe_float(zone.get("price"))

        if price is None:
            continue

        candidates.append(zone)

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: _safe_float(
            item.get("strength"),
            0,
        ),
        reverse=True,
    )

    return candidates[0]


def _find_protected_level(
    structure: Optional[Dict[str, Any]],
    direction: str,
):
    if not structure:
        return None

    key = (
        "protected_low"
        if direction == BULLISH
        else "protected_high"
    )

    value = structure.get(key)

    if value is None:
        return None

    if isinstance(value, dict):
        price = _safe_float(value.get("price"))

        if price is None:
            return None

        return {
            "price": price,
            "source": "PROTECTED_STRUCTURE",
            "raw": value,
        }

    price = _safe_float(value)

    if price is None:
        return None

    return {
        "price": price,
        "source": "PROTECTED_STRUCTURE",
    }


def _find_liquidity_level(
    liquidity: Optional[Dict[str, Any]],
    direction: str,
    entry: float,
):
    """
    Finds a potential liquidity-based invalidation level.

    LONG:
        Prefer a sell-side level below entry.

    SHORT:
        Prefer a buy-side level above entry.

    Liquidity is used only as a fallback.
    """

    if not liquidity:
        return None

    levels = liquidity.get("levels", [])

    if not isinstance(levels, list):
        return None

    candidates = []

    for level in levels:
        if not isinstance(level, dict):
            continue

        price = _safe_float(
            level.get("level_price", level.get("price"))
        )

        if price is None:
            continue

        side = str(
            level.get("side", "")
        ).upper()

        if direction == BULLISH:
            valid_side = (
                price < entry
                and side in {"SELL_SIDE", "SELL"}
            )
        else:
            valid_side = (
                price > entry
                and side in {"BUY_SIDE", "BUY"}
            )

        if valid_side:
            candidates.append(level)

    if not candidates:
        return None

    if direction == BULLISH:
        candidates.sort(
            key=lambda item: _safe_float(
                item.get("level_price", item.get("price")),
                0,
            ),
            reverse=True,
        )
    else:
        candidates.sort(
            key=lambda item: _safe_float(
                item.get("level_price", item.get("price")),
                float("inf"),
            ),
        )

    selected = candidates[0]

    return {
        "price": _safe_float(
            selected.get(
                "level_price",
                selected.get("price"),
            )
        ),
        "source": "LIQUIDITY",
        "raw": selected,
    }


def _select_stop_loss(
    direction: str,
    entry: float,
    atr: float,
    structure: Optional[Dict[str, Any]],
    sr_zone: Optional[Dict[str, Any]],
    liquidity: Optional[Dict[str, Any]],
):
    """
    Stop-loss hierarchy:

    1. Protected structure
    2. Directional S/R
    3. Liquidity
    4. ATR fallback

    A structural level is accepted only if it is
    on the correct side of entry.
    """

    base_distance = atr * 1.5

    protected = _find_protected_level(
        structure,
        direction,
    )

    sr_price = None

    if sr_zone:
        sr_price = _safe_float(
            sr_zone.get("price")
        )

    liquidity_level = _find_liquidity_level(
        liquidity,
        direction,
        entry,
    )

    candidates = []

    if protected:
        candidates.append(protected)

    if sr_price is not None:
        candidates.append({
            "price": sr_price,
            "source": "SR_ZONE",
            "raw": sr_zone,
        })

    if liquidity_level:
        candidates.append(liquidity_level)

    valid_candidates = []

    for item in candidates:
        price = _safe_float(item.get("price"))

        if price is None:
            continue

        if direction == BULLISH and price < entry:
            valid_candidates.append(item)

        elif direction == BEARISH and price > entry:
            valid_candidates.append(item)

    if direction == BULLISH:
        valid_candidates.sort(
            key=lambda item: item["price"],
            reverse=True,
        )
    else:
        valid_candidates.sort(
            key=lambda item: item["price"],
        )

    selected = None

    if valid_candidates:
        selected = valid_candidates[0]

    if selected is not None:
        structural_price = selected["price"]

        if direction == BULLISH:
            distance = entry - structural_price

            if distance >= base_distance:
                stop = structural_price
                source = selected["source"]
            else:
                stop = entry - base_distance
                source = "ATR_FALLBACK"

        else:
            distance = structural_price - entry

            if distance >= base_distance:
                stop = structural_price
                source = selected["source"]
            else:
                stop = entry + base_distance
                source = "ATR_FALLBACK"

    else:
        if direction == BULLISH:
            stop = entry - base_distance
        else:
            stop = entry + base_distance

        source = "ATR_FALLBACK"

    if source == "ATR_FALLBACK":
        reason = (
            "No valid structural invalidation level "
            "with sufficient ATR distance was available."
        )
    else:
        reason = (
            f"Stop-loss selected from {source} "
            "using the directional invalidation hierarchy."
        )

    return {
        "stop_loss": round(stop, 5),
        "source": source,
        "reason": reason,
    }


def _calculate_targets(
    direction: str,
    entry: float,
    stop_loss: float,
):
    if direction == BULLISH:
        risk = entry - stop_loss

        if risk <= 0:
            return None

        tp1 = entry + risk * 1.5
        tp2 = entry + risk * 2.0
        tp3 = entry + risk * 3.0

    else:
        risk = stop_loss - entry

        if risk <= 0:
            return None

        tp1 = entry - risk * 1.5
        tp2 = entry - risk * 2.0
        tp3 = entry - risk * 3.0

    return {
        "entry": round(entry, 5),
        "stop_loss": round(stop_loss, 5),
        "tp1": round(tp1, 5),
        "tp2": round(tp2, 5),
        "tp3": round(tp3, 5),
        "take_profit_1": round(tp1, 5),
        "take_profit_2": round(tp2, 5),
        "take_profit_3": round(tp3, 5),
        "risk_distance": round(risk, 5),
        "rr": 2.0,
        "rr_tp1": 1.5,
        "rr_tp2": 2.0,
        "rr_tp3": 3.0,
    }


def _confirmation_requirements(
    direction: str,
    mtf: Dict[str, Any],
    confluence: Dict[str, Any],
    price_action: Dict[str, Any],
    sr_zone: Optional[Dict[str, Any]],
):
    requirements = []

    requirements.append({
        "condition": "MTF directional alignment",
        "status": (
            "PASS"
            if mtf.get("macro_bias") == direction
            else "WAIT"
        ),
    })

    setup_state = mtf.get("setup_state")

    requirements.append({
        "condition": "15M setup context",
        "status": (
            "PASS"
            if setup_state in {
                "ALIGNED",
                "PULLBACK_ENDING_OR_RETEST",
            }
            else "WAIT"
        ),
    })

    entry_state = mtf.get("entry_state")

    requirements.append({
        "condition": "5M entry context",
        "status": (
            "PASS"
            if entry_state in {
                "ENTRY_CONFIRMATION",
                "CONFIRMED",
            }
            else "WAIT"
        ),
    })

    liquidity_state = (
        confluence
        .get("liquidity", {})
        .get("state")
    )

    requirements.append({
        "condition": "Liquidity context",
        "status": (
            "PASS"
            if liquidity_state == "ALIGNED"
            else "WAIT"
        ),
    })

    requirements.append({
        "condition": "Directional S/R context",
        "status": (
            "PASS"
            if sr_zone is not None
            else "WAIT"
        ),
    })

    pa_direction = (
        price_action or {}
    ).get("direction", NEUTRAL)

    requirements.append({
        "condition": "Directional price action",
        "status": (
            "PASS"
            if pa_direction == direction
            else "WAIT"
        ),
    })

    return requirements


def generate_setup(
    df,
    mtf: Optional[Dict[str, Any]],
    confluence: Optional[Dict[str, Any]],
    structure: Optional[Dict[str, Any]],
    levels: Optional[Dict[str, Any]],
    liquidity: Optional[Dict[str, Any]],
    price_action: Optional[Dict[str, Any]],
    min_rr: float = 2.0,
):
    """
    Setup Generator V3.

    Responsibilities:
    - Generate deterministic entry, SL and TP levels.
    - Select SL using an invalidation hierarchy.
    - Validate directional risk.
    - Preserve bias != entry.
    - Never calculate win probability.
    """

    if df is None or len(df) < 20:
        return {
            "status": "NO TRADE",
            "reason": "Insufficient market data.",
        }

    if not mtf:
        return {
            "status": "NO TRADE",
            "reason": "MTF analysis unavailable.",
        }

    if not confluence:
        return {
            "status": "NO TRADE",
            "reason": "Confluence analysis unavailable.",
        }

    macro_bias = mtf.get(
        "macro_bias",
        NEUTRAL,
    )

    if macro_bias not in {
        BULLISH,
        BEARISH,
    }:
        return {
            "status": "NO TRADE",
            "reason": "No directional macro bias.",
        }

    trade_direction = _trade_direction(macro_bias)

    last = df.iloc[-1]

    entry = _safe_float(
        last.get("close")
    )

    atr = _safe_float(
        last.get("atr")
    )

    if entry is None or entry <= 0:
        return {
            "status": "NO TRADE",
            "reason": "Current price unavailable.",
        }

    if atr is None or atr <= 0:
        return {
            "status": "NO TRADE",
            "reason": "ATR unavailable.",
        }

    sr_zone = _find_directional_zone(
        levels,
        macro_bias,
    )

    stop_result = _select_stop_loss(
        direction=macro_bias,
        entry=entry,
        atr=atr,
        structure=structure,
        sr_zone=sr_zone,
        liquidity=liquidity,
    )

    stop_loss = stop_result["stop_loss"]

    target_result = _calculate_targets(
        direction=macro_bias,
        entry=entry,
        stop_loss=stop_loss,
    )

    if target_result is None:
        return {
            "status": "NO TRADE",
            "reason": "Unable to construct valid risk levels.",
        }

    risk_distance = target_result["risk_distance"]

    rr_tp2 = target_result["rr_tp2"]

    risk_validation = validate_invalidation(
        direction=trade_direction,
        entry=entry,
        stop_loss=stop_loss,
    )

    if not risk_validation.get("valid", False):
        return {
            "status": "NO TRADE",
            "reason": "Invalid stop-loss relationship.",
            "risk_validation": risk_validation,
        }

    requirements = _confirmation_requirements(
        direction=macro_bias,
        mtf=mtf,
        confluence=confluence,
        price_action=price_action,
        sr_zone=sr_zone,
    )

    passed = sum(
        1
        for item in requirements
        if item["status"] == "PASS"
    )

    total = len(requirements)

    confirmation_ratio = (
        passed / total
        if total
        else 0
    )

    mtf_decision = mtf.get(
        "decision",
        "WAIT_FOR_SETUP",
    )

    liquidity_state = (
        confluence
        .get("liquidity", {})
        .get("state")
    )

    pa_state = (
        confluence
        .get("price_action", {})
        .get("state")
    )

    hard_conflict = (
        liquidity_state == "CONFLICTING"
        or pa_state == "CONFLICTING"
    )

    entry_confirmed = (
        mtf_decision == "ENTRY_CONFIRMATION_POSSIBLE"
        and confirmation_ratio >= 0.66
        and not hard_conflict
        and rr_tp2 >= min_rr
    )

    if hard_conflict:
        status = "WAIT"
        reason = (
            "Directional conflict detected. "
            "Waiting for confirmation."
        )

    elif entry_confirmed:
        status = "SETUP VALID"
        reason = (
            "Directional structure and setup "
            "conditions are aligned."
        )

    else:
        status = "WAIT"
        reason = (
            "Setup direction exists, but entry "
            "confirmation is incomplete."
        )

    if macro_bias == BULLISH:
        invalidation_reason = (
            "Bullish thesis invalid above? No. "
            "Bullish thesis is invalid below the "
            "selected stop-loss level."
        )
    else:
        invalidation_reason = (
            "Bearish thesis is invalid above the "
            "selected stop-loss level."
        )

    return {
        "status": status,
        "direction": trade_direction,
        "bias": macro_bias,

        "entry": target_result["entry"],
        "stop_loss": target_result["stop_loss"],

        "tp1": target_result["tp1"],
        "tp2": target_result["tp2"],
        "tp3": target_result["tp3"],

        "take_profit_1": target_result["take_profit_1"],
        "take_profit_2": target_result["take_profit_2"],
        "take_profit_3": target_result["take_profit_3"],

        "risk_distance": risk_distance,

        "rr": target_result["rr"],
        "rr_tp1": target_result["rr_tp1"],
        "rr_tp2": target_result["rr_tp2"],
        "rr_tp3": target_result["rr_tp3"],

        "confirmation": {
            "passed": passed,
            "required": total,
            "ratio": round(
                confirmation_ratio,
                3,
            ),
            "requirements": requirements,
        },

        "context": {
            "mtf_decision": mtf_decision,
            "setup_state": mtf.get("setup_state"),
            "entry_state": mtf.get("entry_state"),
            "sr_zone": sr_zone,
            "protected_level": _find_protected_level(
                structure,
                macro_bias,
            ),
            "liquidity_state": liquidity_state,
            "price_action_state": pa_state,
        },

        "risk_validation": risk_validation,

        "stop_loss_details": {
            "source": stop_result["source"],
            "reason": stop_result["reason"],
        },

        "invalidation": {
            "level": target_result["stop_loss"],
            "reason": invalidation_reason,
        },

        "reason": reason,

        "methodology": {
            "type": "Deterministic setup construction V3",
            "bias_source": "4H macro structure",
            "entry_source": "MTF + liquidity + S/R + price action",
            "risk_model": (
                "Protected structure → S/R → "
                "Liquidity → ATR fallback"
            ),
            "rr_target": min_rr,
            "prediction": "None",
            "win_probability": "Not calculated",
        },
    }