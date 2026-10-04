from datetime import datetime, timezone

import MetaTrader5 as mt5


MAX_TICK_AGE_SECONDS = 300


def get_current_price(
    symbol: str = "XAUUSD",
    max_age_seconds: int = MAX_TICK_AGE_SECONDS,
) -> dict:
    if not mt5.initialize():
        raise RuntimeError(
            f"MT5 initialize failed: {mt5.last_error()}"
        )

    try:
        info = mt5.symbol_info(symbol)

        if info is None:
            raise ValueError(f"Symbol not found: {symbol}")

        if not info.visible:
            if not mt5.symbol_select(symbol, True):
                raise RuntimeError(
                    f"Could not select symbol: {symbol}"
                )

        tick = mt5.symbol_info_tick(symbol)

        if tick is None:
            raise RuntimeError(
                f"No tick available for {symbol}"
            )

        tick_time = datetime.fromtimestamp(
            tick.time,
            tz=timezone.utc,
        )

        now = datetime.now(timezone.utc)
        age_seconds = (now - tick_time).total_seconds()

        return {
            "symbol": symbol,
            "bid": float(tick.bid),
            "ask": float(tick.ask),
            "mid": float((tick.bid + tick.ask) / 2.0),
            "timestamp": tick_time.isoformat(),
            "age_seconds": round(age_seconds, 3),
            "fresh": age_seconds <= max_age_seconds,
        }

    finally:
        mt5.shutdown()
