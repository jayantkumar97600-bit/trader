from datetime import datetime, timezone
from typing import Any

from app.services.journal import close_trade, get_open_trades
from app.services.mt5_price import get_current_price


def check_exit(
    direction: str,
    bid: float,
    ask: float,
    stop_loss: float,
    take_profit: float,
) -> dict:
    direction = direction.upper()

    if direction == "LONG":
        if bid <= stop_loss:
            return {
                "should_close": True,
                "reason": "STOP_LOSS",
                "exit_price": bid,
            }

        if bid >= take_profit:
            return {
                "should_close": True,
                "reason": "TAKE_PROFIT",
                "exit_price": bid,
            }

    elif direction == "SHORT":
        if ask >= stop_loss:
            return {
                "should_close": True,
                "reason": "STOP_LOSS",
                "exit_price": ask,
            }

        if ask <= take_profit:
            return {
                "should_close": True,
                "reason": "TAKE_PROFIT",
                "exit_price": ask,
            }

    else:
        raise ValueError(f"Invalid direction: {direction}")

    return {
        "should_close": False,
        "reason": None,
        "exit_price": None,
    }


def monitor_open_trades(
    symbol: str = "XAUUSD",
    max_tick_age_seconds: int = 300,
    price: dict[str, Any] | None = None,
) -> dict:
    """
    Check all OPEN paper trades against a current price snapshot.

    Safety:
    - stale MT5 ticks cause NO ACTION
    - only OPEN trades are checked
    - no real MT5 orders are ever submitted
    - an injected price snapshot may be supplied by the runner
    """

    if price is None:
        price = get_current_price(
            symbol=symbol,
            max_age_seconds=max_tick_age_seconds,
        )

    if not price["fresh"]:
        return {
            "status": "STALE_PRICE",
            "action": "NO_ACTION",
            "price": price,
            "checked": 0,
            "closed": [],
        }

    open_trades = get_open_trades()
    closed = []

    for trade in open_trades:
        if trade["asset"] != symbol:
            continue

        result = check_exit(
            direction=trade["direction"],
            bid=price["bid"],
            ask=price["ask"],
            stop_loss=float(trade["stop_loss"]),
            take_profit=float(trade["take_profit"]),
        )

        if not result["should_close"]:
            continue

        closed_trade = close_trade(
            trade_id=int(trade["id"]),
            exit_price=float(result["exit_price"]),
            exit_timestamp=price["timestamp"],
            exit_reason=result["reason"],
            fees=0.0,
        )

        closed.append(closed_trade)

    return {
        "status": "OK",
        "action": "CHECKED",
        "price": price,
        "checked": len(open_trades),
        "closed": closed,
    }
