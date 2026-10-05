from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd


DATA_FILE = Path("../data/mt5/XAUUSD_M15.csv")
TIMEFRAME_SECONDS = 15 * 60
MAX_DATA_AGE_SECONDS = 20 * 60


def get_mt5_latest_completed_m1_timestamp(
    symbol: str = "XAUUSD",
) -> pd.Timestamp:
    if not mt5.initialize():
        raise RuntimeError(
            f"MT5 initialization failed: {mt5.last_error()}"
        )

    try:
        rates = mt5.copy_rates_from_pos(
            symbol,
            mt5.TIMEFRAME_M1,
            1,
            1,
        )

        if rates is None:
            raise RuntimeError(
                f"MT5 returned no M1 data: {mt5.last_error()}"
            )

        if len(rates) == 0:
            raise RuntimeError(
                f"No completed M1 candle available for {symbol}."
            )

        return pd.Timestamp(
            pd.to_datetime(
                int(rates[0]["time"]),
                unit="s",
                utc=True,
            )
        )

    finally:
        mt5.shutdown()


def get_latest_completed_candle_age_seconds(
    current_timestamp=None,
    data_file=DATA_FILE,
):
    if not data_file.exists():
        return {
            "status": "ERROR",
            "reason": "DATA_FILE_NOT_FOUND",
        }

    df = pd.read_csv(
        data_file,
        usecols=["timestamp"],
        parse_dates=["timestamp"],
    )

    if df.empty:
        return {
            "status": "ERROR",
            "reason": "NO_CANDLES",
        }

    latest_open = pd.Timestamp(df["timestamp"].iloc[-1])

    if latest_open.tzinfo is None:
        latest_open = latest_open.tz_localize("UTC")
    else:
        latest_open = latest_open.tz_convert("UTC")

    completion = latest_open + pd.Timedelta(
        seconds=TIMEFRAME_SECONDS
    )

    try:
        mt5_latest_m1 = get_mt5_latest_completed_m1_timestamp()
    except Exception as exc:
        return {
            "status": "ERROR",
            "reason": "MT5_TIME_UNAVAILABLE",
            "error": str(exc),
            "latest_candle_open": latest_open.isoformat(),
            "completion_timestamp": completion.isoformat(),
        }

    # The M15 candle has not completed yet according to MT5.
    if completion > mt5_latest_m1 + pd.Timedelta(minutes=1):
        return {
            "status": "WAITING_FOR_COMPLETION",
            "latest_candle_open": latest_open.isoformat(),
            "completion_timestamp": completion.isoformat(),
            "mt5_latest_completed_m1": mt5_latest_m1.isoformat(),
        }

    # Calculate age using MT5 candle timestamps, not local PC time.
    age_seconds = (
        mt5_latest_m1 + pd.Timedelta(minutes=1) - completion
    ).total_seconds()

    if age_seconds > MAX_DATA_AGE_SECONDS:
        return {
            "status": "STALE_DATA",
            "latest_candle_open": latest_open.isoformat(),
            "completion_timestamp": completion.isoformat(),
            "mt5_latest_completed_m1": mt5_latest_m1.isoformat(),
            "age_seconds": age_seconds,
            "max_allowed_age_seconds": MAX_DATA_AGE_SECONDS,
        }

    return {
        "status": "OK",
        "latest_candle_open": latest_open.isoformat(),
        "completion_timestamp": completion.isoformat(),
        "mt5_latest_completed_m1": mt5_latest_m1.isoformat(),
        "age_seconds": age_seconds,
        "max_allowed_age_seconds": MAX_DATA_AGE_SECONDS,
    }
