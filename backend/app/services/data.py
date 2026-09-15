from pathlib import Path
import pandas as pd

TIMEFRAME_FILES = {
    "1m": "M1", "3m": "M3", "5m": "M5", "15m": "M15",
    "30m": "M30", "1h": "H1", "4h": "H4", "1d": "D1", "1w": "W1",
}


def load_csv(path, limit=None):
    # limit is intentionally used for the API/chart/analysis hot path so a
    # multi-million-row M1 file is never pushed into the browser.
    if limit:
        df = pd.read_csv(path, usecols=["timestamp", "open", "high", "low", "close", "volume"]).tail(limit)
    else:
        df = pd.read_csv(path)
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna().drop_duplicates("timestamp").sort_values("timestamp")
    return df.reset_index(drop=True)


def timeframe_path(data_dir: Path, timeframe: str, asset: str = "XAUUSD") -> Path:
    tf = timeframe.lower()
    suffix = TIMEFRAME_FILES.get(tf)
    if not suffix:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    return data_dir / "mt5" / f"{asset}_{suffix}.csv"
