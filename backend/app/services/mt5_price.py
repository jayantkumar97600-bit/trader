from datetime import datetime, timezone
from typing import Any

import MetaTrader5 as mt5


def _utc_from_timestamp(value: int | float) -> datetime:
    return datetime.fromtimestamp(float(value), tz=timezone.utc)


def get_current_price(
    symbol: str = "XAUUSD",
    max_age_seconds: int = 300,
) -> dict[str, Any]:
    """
    Get current MT5 price.

    IMPORTANT:
    MT5 tick timestamps are based on the broker/MT5 server clock.
    We therefore do NOT compare tick.time against Python's local UTC
    clock because the two clocks can have different offsets.

    Instead, freshness is measured against the latest M1 bar available
    from the same MT5 feed.
    """

    if not mt5.initialize():
        error = mt5.last_error()
        raise RuntimeError(f"MT5 initialize failed: {error}")

    try:
        if not mt5.symbol_select(symbol, True):
            error = mt5.last_error()
            raise RuntimeError(f"MT5 symbol_select failed for {symbol}: {error}")

        tick = mt5.symbol_info_tick(symbol)

        if tick is None:
            error = mt5.last_error()
            raise RuntimeError(f"No tick available for {symbol}: {error}")

        if tick.bid is None or tick.ask is None:
            raise RuntimeError(f"Invalid tick received for {symbol}")

        if float(tick.bid) <= 0 or float(tick.ask) <= 0:
            raise RuntimeError(
                f"Invalid MT5 price for {symbol}: "
                f"bid={tick.bid}, ask={tick.ask}"
            )

        tick_timestamp = _utc_from_timestamp(tick.time)

        # Current M1 bar from the SAME MT5 server/feed.
        current_m1 = mt5.copy_rates_from_pos(
            symbol,
            mt5.TIMEFRAME_M1,
            0,
            1,
        )

        if current_m1 is None or len(current_m1) == 0:
            error = mt5.last_error()
            raise RuntimeError(
                f"Unable to read current M1 candle for {symbol}: {error}"
            )

        current_m1_timestamp = _utc_from_timestamp(
            int(current_m1[0]["time"])
        )

        # Both timestamps come from MT5.
        # This avoids the previous ~3 hour local-clock mismatch.
        age_seconds = max(
            0.0,
            (current_m1_timestamp - tick_timestamp).total_seconds(),
        )

        fresh = age_seconds <= float(max_age_seconds)

        bid = float(tick.bid)
        ask = float(tick.ask)
        mid = (bid + ask) / 2.0

        return {
            "symbol": symbol,
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "timestamp": tick_timestamp.isoformat(),
            "age_seconds": age_seconds,
            "fresh": fresh,
            "max_age_seconds": max_age_seconds,
            "clock_source": "MT5_SERVER_FEED",
            "reference_m1_timestamp": current_m1_timestamp.isoformat(),
        }

    finally:
        mt5.shutdown()
