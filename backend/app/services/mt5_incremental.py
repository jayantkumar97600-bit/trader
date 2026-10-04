from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd


SYMBOL = "XAUUSD"
DATA_DIR = Path("../data/mt5")
M1_FILE = DATA_DIR / "XAUUSD_M1.csv"

TIMEFRAME_FILES = {
    "M3": "3min",
    "M5": "5min",
    "M15": "15min",
    "M30": "30min",
    "H1": "1h",
    "H4": "4h",
    "D1": "1D",
    "W1": "1W",
}


def get_last_timestamp() -> pd.Timestamp:
    if not M1_FILE.exists():
        raise FileNotFoundError(f"M1 data not found: {M1_FILE}")

    df = pd.read_csv(
        M1_FILE,
        usecols=["timestamp"],
        parse_dates=["timestamp"],
    )

    if df.empty:
        raise ValueError("M1 CSV is empty.")

    return pd.Timestamp(df["timestamp"].iloc[-1])


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    x = df.copy()
    x["timestamp"] = pd.to_datetime(
        x["timestamp"],
        utc=True,
    )

    x = x.set_index("timestamp")

    result = x.resample(rule).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )

    return (
        result
        .dropna()
        .reset_index()
    )


def refresh_incremental() -> dict:
    last_timestamp = get_last_timestamp()

    if not mt5.initialize():
        raise RuntimeError(
            f"MT5 initialization failed: {mt5.last_error()}"
        )

    try:
        info = mt5.symbol_info(SYMBOL)

        if info is None:
            raise RuntimeError(f"{SYMBOL} not found.")

        if not info.visible:
            if not mt5.symbol_select(SYMBOL, True):
                raise RuntimeError(
                    f"Could not select {SYMBOL}."
                )

        rates = mt5.copy_rates_from(
            SYMBOL,
            mt5.TIMEFRAME_M1,
            last_timestamp.to_pydatetime(),
            10000,
        )

        if rates is None:
            raise RuntimeError(
                f"MT5 returned no data: {mt5.last_error()}"
            )

        new_df = pd.DataFrame(rates)

        if new_df.empty:
            return {
                "status": "NO_NEW_DATA",
                "last_timestamp": str(last_timestamp),
                "new_candles": 0,
            }

        new_df["timestamp"] = pd.to_datetime(
            new_df["time"],
            unit="s",
            utc=True,
        )

        new_df = new_df.rename(
            columns={"tick_volume": "volume"}
        )

        new_df = new_df[
            [
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        ]

        new_df = new_df[
            new_df["timestamp"] > last_timestamp
        ]

        if new_df.empty:
            return {
                "status": "NO_NEW_DATA",
                "last_timestamp": str(last_timestamp),
                "new_candles": 0,
            }

        existing = pd.read_csv(
            M1_FILE,
            parse_dates=["timestamp"],
        )

        combined = pd.concat(
            [existing, new_df],
            ignore_index=True,
        )

        combined = (
            combined
            .drop_duplicates("timestamp", keep="last")
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

        combined.to_csv(
            M1_FILE,
            index=False,
        )

        # Rebuild timeframe files from the updated M1 data.
        for name, rule in TIMEFRAME_FILES.items():
            tf = resample_ohlcv(
                combined,
                rule,
            )

            tf.to_csv(
                DATA_DIR / f"XAUUSD_{name}.csv",
                index=False,
            )

        return {
            "status": "UPDATED",
            "previous_last_timestamp": str(last_timestamp),
            "new_candles": int(len(new_df)),
            "last_timestamp": str(
                combined["timestamp"].iloc[-1]
            ),
        }

    finally:
        mt5.shutdown()


if __name__ == "__main__":
    result = refresh_incremental()
    print(result)
