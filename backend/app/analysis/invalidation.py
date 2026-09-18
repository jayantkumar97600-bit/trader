
from typing import Any, Dict


LONG = "LONG"
SHORT = "SHORT"


def _number(value: Any):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_invalidation(
    direction: str,
    entry: Any,
    stop_loss: Any,
    current_price: Any = None,
) -> Dict[str, Any]:
    """
    Validates the basic structural relationship between
    trade direction, entry and stop-loss.

    This function does not predict prices.
    """

    direction = str(direction or "").upper().strip()

    entry_value = _number(entry)
    stop_value = _number(stop_loss)
    current_value = _number(current_price)

    if direction not in {LONG, SHORT}:
        return {
            "status": "INVALID",
            "valid": False,
            "reason": "Trade direction must be LONG or SHORT.",
        }

    if entry_value is None or stop_value is None:
        return {
            "status": "INVALID",
            "valid": False,
            "reason": "Entry and stop-loss must be numeric.",
        }

    if entry_value <= 0 or stop_value <= 0:
        return {
            "status": "INVALID",
            "valid": False,
            "reason": "Entry and stop-loss must be positive.",
        }

    if direction == LONG and stop_value >= entry_value:
        return {
            "status": "INVALID",
            "valid": False,
            "reason": "LONG stop-loss must be below entry.",
        }

    if direction == SHORT and stop_value <= entry_value:
        return {
            "status": "INVALID",
            "valid": False,
            "reason": "SHORT stop-loss must be above entry.",
        }

    result = {
        "status": "VALID",
        "valid": True,
        "direction": direction,
        "entry": entry_value,
        "stop_loss": stop_value,
        "reason": (
            "LONG invalidation is below entry."
            if direction == LONG
            else "SHORT invalidation is above entry."
        ),
    }

    if current_value is not None:
        if direction == LONG and current_value <= stop_value:
            result["status"] = "TRIGGERED"
            result["valid"] = False
            result["reason"] = "LONG stop-loss level has been reached."

        elif direction == SHORT and current_value >= stop_value:
            result["status"] = "TRIGGERED"
            result["valid"] = False
            result["reason"] = "SHORT stop-loss level has been reached."

    return result