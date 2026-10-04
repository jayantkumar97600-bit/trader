from pathlib import Path
import pandas as pd

DATA_FILE = Path("../data/mt5/XAUUSD_M15.csv")
TIMEFRAME_SECONDS = 15 * 60
MAX_DATA_AGE_SECONDS = 20 * 60


def get_latest_completed_candle_age_seconds(
    current_timestamp,
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

    latest_open = df["timestamp"].iloc[-1]
    current = pd.Timestamp(current_timestamp)

    if latest_open.tzinfo is None:
        latest_open = latest_open.tz_localize("UTC")

    if current.tzinfo is None:
        current = current.tz_localize("UTC")

    completion = latest_open + pd.Timedelta(seconds=TIMEFRAME_SECONDS)
    age_seconds = (current - completion).total_seconds()

    if age_seconds < 0:
        return {
            "status": "WAITING_FOR_COMPLETION",
            "latest_candle_open": latest_open.isoformat(),
            "completion_timestamp": completion.isoformat(),
            "current_timestamp": current.isoformat(),
            "age_seconds": age_seconds,
        }

    if age_seconds > MAX_DATA_AGE_SECONDS:
        return {
            "status": "STALE_DATA",
            "latest_candle_open": latest_open.isoformat(),
            "completion_timestamp": completion.isoformat(),
            "current_timestamp": current.isoformat(),
            "age_seconds": age_seconds,
            "max_allowed_age_seconds": MAX_DATA_AGE_SECONDS,
        }

    return {
        "status": "OK",
        "latest_candle_open": latest_open.isoformat(),
        "completion_timestamp": completion.isoformat(),
        "current_timestamp": current.isoformat(),
        "age_seconds": age_seconds,
        "max_allowed_age_seconds": MAX_DATA_AGE_SECONDS,
    }
