from app.services.journal import add_trade, close_trade
from app.services.paper_monitor import check_exit


def simulate_monitor(
    direction: str,
    entry: float,
    stop_loss: float,
    take_profit: float,
    bid: float,
    ask: float,
) -> dict:
    """
    Simulate one fresh MT5 tick against a paper trade.

    This does NOT connect to MT5 and does NOT create/close
    any database trade.
    """

    result = check_exit(
        direction=direction,
        bid=bid,
        ask=ask,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )

    return {
        "direction": direction,
        "bid": bid,
        "ask": ask,
        "should_close": result["should_close"],
        "reason": result["reason"],
        "exit_price": result["exit_price"],
    }
