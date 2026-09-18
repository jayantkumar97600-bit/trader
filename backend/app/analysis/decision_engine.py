
from typing import Any, Dict, List


BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"

LONG = "LONG"
SHORT = "SHORT"

WAIT = "WAIT"
NO_TRADE = "NO_TRADE"
ENTRY_READY = "ENTRY_READY"


def _text(value: Any) -> str:
    return str(value or "").upper().strip()


def _opposite(direction: str) -> str:
    if direction == BULLISH:
        return BEARISH
    if direction == BEARISH:
        return BULLISH
    return NEUTRAL


def _trade_direction(bias: str) -> str:
    if bias == BULLISH:
        return LONG
    if bias == BEARISH:
        return SHORT
    return ""


def _status_of(check: Any) -> str:
    if isinstance(check, dict):
        return _text(check.get("status"))
    return _text(check)


def _is_pass(check: Any) -> bool:
    return _status_of(check) in {"PASS", "OK", "CONFIRMED"}


def _is_fresh_pass(check: Any) -> bool:
    if not isinstance(check, dict):
        return False

    status = _status_of(check)
    fresh = check.get("fresh")

    if status in {"STALE", "WAIT", "FAIL", "NONE"}:
        return False

    if fresh is False:
        return False

    return status in {"PASS", "OK", "CONFIRMED"}


def _extract_confirmation_checks(
    entry_confirmation: Dict[str, Any],
) -> Dict[str, Any]:
    checks = entry_confirmation.get("checks", {})

    if not isinstance(checks, dict):
        checks = {}

    return checks


def _check_direction_alignment(
    mtf: Dict[str, Any],
    direction: str,
) -> bool:
    macro_bias = _text(mtf.get("macro_bias"))
    major_structure = _text(mtf.get("major_structure"))

    if direction == SHORT:
        expected_bias = BEARISH
    elif direction == LONG:
        expected_bias = BULLISH
    else:
        return False

    if macro_bias != expected_bias:
        return False

    if major_structure not in {"ALIGNED", "CONFIRMED", ""}:
        return False

    return True


def _price_action_confirms(
    price_action: Dict[str, Any],
    direction: str,
) -> bool:
    if not isinstance(price_action, dict):
        return False

    pa_direction = _text(price_action.get("direction"))
    pa_state = _text(price_action.get("state"))

    expected_bias = (
        BULLISH if direction == LONG else BEARISH
    )

    return (
        pa_direction == expected_bias
        and pa_state in {"CONFIRMING", "CONFIRMED"}
    )


def _risk_reward_valid(
    setup: Dict[str, Any],
    min_rr: float,
) -> bool:
    if not isinstance(setup, dict):
        return False

    rr = setup.get("rr")

    try:
        rr_value = float(rr)
    except (TypeError, ValueError):
        return False

    return rr_value >= float(min_rr)


def _setup_direction_valid(
    setup: Dict[str, Any],
    direction: str,
) -> bool:
    if not isinstance(setup, dict):
        return False

    setup_direction = _text(setup.get("direction"))

    return setup_direction == direction


def _has_valid_prices(setup: Dict[str, Any]) -> bool:
    if not isinstance(setup, dict):
        return False

    required = [
        "entry",
        "stop_loss",
        "take_profit_1",
    ]

    for field in required:
        value = setup.get(field)

        if value is None:
            return False

        try:
            if float(value) <= 0:
                return False
        except (TypeError, ValueError):
            return False

    return True


def _invalidation_state(
    setup: Dict[str, Any],
    direction: str,
) -> Dict[str, Any]:
    if not isinstance(setup, dict):
        return {
            "status": "UNKNOWN",
            "reason": "Setup data unavailable.",
        }

    entry = setup.get("entry")
    stop_loss = setup.get("stop_loss")

    if entry is None or stop_loss is None:
        return {
            "status": "UNKNOWN",
            "reason": "Entry or stop-loss is unavailable.",
        }

    try:
        entry_value = float(entry)
        stop_value = float(stop_loss)
    except (TypeError, ValueError):
        return {
            "status": "UNKNOWN",
            "reason": "Entry or stop-loss is invalid.",
        }

    if direction == LONG and stop_value >= entry_value:
        return {
            "status": "INVALID",
            "reason": "Long stop-loss must be below entry.",
        }

    if direction == SHORT and stop_value <= entry_value:
        return {
            "status": "INVALID",
            "reason": "Short stop-loss must be above entry.",
        }

    return {
        "status": "VALID",
        "reason": "Entry and stop-loss relationship is valid.",
    }


def make_decision(
    mtf: Dict[str, Any],
    confluence: Dict[str, Any],
    entry_confirmation: Dict[str, Any],
    setup: Dict[str, Any],
    price_action: Dict[str, Any],
    min_rr: float = 2.0,
) -> Dict[str, Any]:
    """
    Deterministic final decision engine.

    This engine does not predict future prices.
    It only evaluates already-calculated analysis outputs.
    """

    mtf = mtf or {}
    confluence = confluence or {}
    entry_confirmation = entry_confirmation or {}
    setup = setup or {}
    price_action = price_action or {}

    macro_bias = _text(mtf.get("macro_bias"))

    if macro_bias not in {BULLISH, BEARISH}:
        return {
            "status": NO_TRADE,
            "decision": NO_TRADE,
            "direction": "",
            "bias": macro_bias or NEUTRAL,
            "entry_ready": False,
            "reasons": [
                "Macro bias is neutral or unavailable.",
            ],
            "failed_gates": [
                "MACRO_BIAS",
            ],
            "passed_gates": [],
            "methodology": {
                "type": "Deterministic hard-gated decision engine",
                "prediction": "None",
                "win_probability": "Not calculated",
            },
        }

    direction = _trade_direction(macro_bias)
    checks = _extract_confirmation_checks(entry_confirmation)

    passed_gates: List[str] = []
    failed_gates: List[str] = []
    reasons: List[str] = []

    # Gate 1: Higher-timeframe directional alignment.
    if _check_direction_alignment(mtf, direction):
        passed_gates.append("MTF_ALIGNMENT")
    else:
        failed_gates.append("MTF_ALIGNMENT")
        reasons.append(
            "Macro bias and major structure are not aligned."
        )

    # Gate 2: Setup direction.
    if _setup_direction_valid(setup, direction):
        passed_gates.append("SETUP_DIRECTION")
    else:
        failed_gates.append("SETUP_DIRECTION")
        reasons.append(
            "Generated setup direction does not match macro bias."
        )

    # Gate 3: Fresh structure confirmation.
    bos_check = checks.get("bos", {})
    choch_check = checks.get("choch", {})

    fresh_structure = (
        _is_fresh_pass(bos_check)
        or _is_fresh_pass(choch_check)
    )

    if fresh_structure:
        passed_gates.append("FRESH_STRUCTURE")
    else:
        failed_gates.append("FRESH_STRUCTURE")
        reasons.append(
            "No fresh BOS or CHoCH confirmation is available."
        )

    # Gate 4: Price action.
    if _price_action_confirms(price_action, direction):
        passed_gates.append("PRICE_ACTION")
    else:
        failed_gates.append("PRICE_ACTION")
        reasons.append(
            "Price action does not confirm the trade direction."
        )

    # Gate 5: Liquidity freshness.
    liquidity_check = checks.get("liquidity", {})

    if _is_fresh_pass(liquidity_check):
        passed_gates.append("FRESH_LIQUIDITY")
    else:
        failed_gates.append("FRESH_LIQUIDITY")
        reasons.append(
            "Fresh liquidity confirmation is unavailable."
        )

    # Gate 6: Retest.
    retest_check = checks.get("retest", {})

    if _is_pass(retest_check):
        passed_gates.append("RETEST")
    else:
        failed_gates.append("RETEST")
        reasons.append(
            "Valid retest confirmation is unavailable."
        )

    # Gate 7: Valid setup prices.
    if _has_valid_prices(setup):
        passed_gates.append("VALID_PRICES")
    else:
        failed_gates.append("VALID_PRICES")
        reasons.append(
            "Entry, stop-loss or take-profit data is invalid."
        )

    # Gate 8: Risk/reward.
    if _risk_reward_valid(setup, min_rr):
        passed_gates.append("RISK_REWARD")
    else:
        failed_gates.append("RISK_REWARD")
        reasons.append(
            f"Risk/reward is below the minimum of 1:{min_rr:.2f}."
        )

    # Gate 9: Invalidation relationship.
    invalidation = _invalidation_state(setup, direction)

    if invalidation["status"] == "VALID":
        passed_gates.append("INVALIDATION_VALID")
    else:
        failed_gates.append("INVALIDATION_VALID")
        reasons.append(invalidation["reason"])

    confirmation_flag = bool(
        entry_confirmation.get("confirmation", False)
    )

    if confirmation_flag and not failed_gates:
        decision = ENTRY_READY
        status = ENTRY_READY
        entry_ready = True
        reasons.append(
            "All mandatory decision gates passed."
        )
    else:
        decision = WAIT
        status = WAIT
        entry_ready = False

        if not reasons:
            reasons.append(
                "Mandatory entry confirmation is not complete."
            )

    return {
        "status": status,
        "decision": decision,
        "direction": direction,
        "bias": macro_bias,
        "entry_ready": entry_ready,
        "passed_gates": passed_gates,
        "failed_gates": failed_gates,
        "passed_count": len(passed_gates),
        "failed_count": len(failed_gates),
        "reasons": reasons,
        "invalidation": invalidation,
        "confirmation": {
            "reported": confirmation_flag,
            "status": _text(entry_confirmation.get("status")),
        },
        "risk_reward": {
            "minimum": float(min_rr),
            "actual": setup.get("rr"),
            "valid": "RISK_REWARD" in passed_gates,
        },
        "methodology": {
            "type": "Deterministic hard-gated decision engine",
            "bias_is_not_entry": True,
            "score_does_not_override_gates": True,
            "prediction": "None",
            "win_probability": "Not calculated",
        },
    }