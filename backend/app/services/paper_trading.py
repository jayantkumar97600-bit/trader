from typing import Any

from app.services.journal import add_trade


STRATEGY_NAME = "BOS_PA_DEVELOPING"
DEFAULT_RISK_PCT = 0.5
MIN_RR = 2.0


def calculate_quantity(
    capital: float,
    risk_pct: float,
    entry: float,
    stop_loss: float,
) -> tuple[float, float]:
    """
    Risk-based position sizing.

    risk_amount = capital * risk_pct / 100
    quantity = risk_amount / abs(entry - stop_loss)
    """

    if capital <= 0:
        raise ValueError("Capital must be positive.")

    if risk_pct <= 0:
        raise ValueError("Risk percentage must be positive.")

    if entry <= 0 or stop_loss <= 0:
        raise ValueError("Entry and stop-loss must be positive.")

    stop_distance = abs(entry - stop_loss)

    if stop_distance <= 0:
        raise ValueError("Entry and stop-loss cannot be equal.")

    risk_amount = capital * (risk_pct / 100.0)
    quantity = risk_amount / stop_distance

    return quantity, risk_amount


def evaluate_signal(analysis: dict[str, Any]) -> dict[str, Any]:
    """
    Frozen research candidate:

        BOS PASS + PA DEVELOPING

    This evaluator intentionally does NOT use the generic
    overall score or Decision Engine entry_ready flag.
    """

    entry_confirmation = analysis.get("entry_confirmation") or {}
    checks = entry_confirmation.get("checks") or {}

    bos = checks.get("bos") or {}
    pa = analysis.get("five_minute_price_action") or {}

    bos_status = str(bos.get("status", "")).upper()
    pa_state = str(pa.get("state", "")).upper()

    direction = str(
        analysis.get("direction")
        or entry_confirmation.get("direction")
        or ""
    ).upper()

    entry = analysis.get("entry")
    stop_loss = analysis.get("stop_loss")
    take_profit = analysis.get("take_profit_1")
    rr = analysis.get("rr")

    reasons = []

    if bos_status != "PASS":
        reasons.append(
            f"BOS requirement failed: {bos_status or 'MISSING'}"
        )

    if pa_state != "DEVELOPING":
        reasons.append(
            f"PA requirement failed: {pa_state or 'MISSING'}"
        )

    if direction not in {"LONG", "SHORT"}:
        reasons.append(
            f"Invalid direction: {direction or 'MISSING'}"
        )

    if entry is None or stop_loss is None or take_profit is None:
        reasons.append("Entry/SL/TP levels are incomplete.")

    if rr is None:
        reasons.append("Risk/reward is unavailable.")
    else:
        try:
            if float(rr) < MIN_RR:
                reasons.append(
                    f"RR {float(rr):.2f} is below minimum {MIN_RR:.2f}."
                )
        except (TypeError, ValueError):
            reasons.append("Risk/reward value is invalid.")

    signal = (
        bos_status == "PASS"
        and pa_state == "DEVELOPING"
        and direction in {"LONG", "SHORT"}
        and entry is not None
        and stop_loss is not None
        and take_profit is not None
        and rr is not None
    )

    if signal:
        try:
            signal = float(rr) >= MIN_RR
        except (TypeError, ValueError):
            signal = False

    return {
        "strategy": STRATEGY_NAME,
        "signal": bool(signal),
        "direction": direction or None,
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "rr": rr,
        "risk_pct": DEFAULT_RISK_PCT,
        "bos_status": bos_status or None,
        "pa_state": pa_state or None,
        "reason": (
            "BOS PASS + PA DEVELOPING"
            if signal
            else "; ".join(reasons)
        ),
    }


def create_paper_trade(
    analysis: dict[str, Any],
    capital: float = 10000.0,
    risk_pct: float = DEFAULT_RISK_PCT,
) -> dict[str, Any]:
    """
    Evaluate the frozen strategy and create an OPEN paper trade
    only when the strategy produces a valid signal.
    """

    signal = evaluate_signal(analysis)

    if not signal["signal"]:
        return {
            "created": False,
            "reason": signal["reason"],
            "signal": signal,
        }

    entry = float(signal["entry"])
    stop_loss = float(signal["stop_loss"])
    take_profit = float(signal["take_profit"])

    quantity, risk_amount = calculate_quantity(
        capital=capital,
        risk_pct=risk_pct,
        entry=entry,
        stop_loss=stop_loss,
    )

    trade = {
        "timestamp": str(
            analysis.get("timestamp")
            or analysis.get("source_timestamp")
            or ""
        ),
        "asset": str(analysis.get("asset") or "XAUUSD"),
        "direction": signal["direction"],
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "quantity": quantity,
        "score": float(analysis.get("score") or 0.0),
        "result": "OPEN",
        "r_multiple": None,
        "notes": signal["reason"],
        "strategy": STRATEGY_NAME,
        "execution_timestamp": None,
        "exit_timestamp": None,
        "exit_price": None,
        "exit_reason": None,
        "risk_pct": risk_pct,
        "fees": 0.0,
    }

    saved = add_trade(trade)

    return {
        "created": True,
        "risk_amount": risk_amount,
        "quantity": quantity,
        "trade": saved,
    }
