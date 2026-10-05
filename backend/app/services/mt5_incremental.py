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

        # ---------------------------------------------------------
        # 1. Get latest available completed M1 candle from MT5.
        # MT5 terminal/server time is the source of truth.
        # ---------------------------------------------------------

        latest_rates = mt5.copy_rates_from_pos(
            SYMBOL,
            mt5.TIMEFRAME_M1,
            1,
            1,
        )

        if latest_rates is None:
            raise RuntimeError(
                f"MT5 returned no latest M1 data: {mt5.last_error()}"
            )

        if len(latest_rates) == 0:
            return {
                "status": "NO_NEW_DATA",
                "last_timestamp": str(last_timestamp),
                "new_candles": 0,
            }

        latest_completed_timestamp = pd.Timestamp(
            pd.to_datetime(
                int(latest_rates[0]["time"]),
                unit="s",
                utc=True,
            )
        )

        # ---------------------------------------------------------
        # 2. If local CSV is already current, stop.
        # ---------------------------------------------------------

        if latest_completed_timestamp <= last_timestamp:
            return {
                "status": "NO_NEW_DATA",
                "last_timestamp": str(last_timestamp),
                "latest_mt5_timestamp": str(
                    latest_completed_timestamp
                ),
                "new_candles": 0,
            }

        # ---------------------------------------------------------
        # 3. Fetch explicitly from local CSV timestamp
        #    through latest completed MT5 candle.
        # ---------------------------------------------------------

        rates = mt5.copy_rates_range(
            SYMBOL,
            mt5.TIMEFRAME_M1,
            last_timestamp.to_pydatetime(),
            latest_completed_timestamp.to_pydatetime(),
        )

        if rates is None:
            raise RuntimeError(
                f"MT5 returned no range data: {mt5.last_error()}"
            )

        new_df = pd.DataFrame(rates)

        if new_df.empty:
            return {
                "status": "NO_NEW_DATA",
                "last_timestamp": str(last_timestamp),
                "latest_mt5_timestamp": str(
                    latest_completed_timestamp
                ),
                "new_candles": 0,
            }

        # ---------------------------------------------------------
        # 4. Normalize MT5 M1 data.
        # ---------------------------------------------------------

        new_df["timestamp"] = pd.to_datetime(
            new_df["time"],
            unit="s",
            utc=True,
        )

        new_df = new_df.rename(
            columns={
                "tick_volume": "volume",
            }
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

        # Only candles strictly newer than local CSV.
        new_df = new_df[
            new_df["timestamp"] > last_timestamp
        ]

        # Never include an incomplete/current M1 candle.
        new_df = new_df[
            new_df["timestamp"] <= latest_completed_timestamp
        ]

        if new_df.empty:
            return {
                "status": "NO_NEW_DATA",
                "last_timestamp": str(last_timestamp),
                "latest_mt5_timestamp": str(
                    latest_completed_timestamp
                ),
                "new_candles": 0,
            }

        # ---------------------------------------------------------
        # 5. Append and deduplicate.
        # ---------------------------------------------------------

        existing = pd.read_csv(
            M1_FILE,
            parse_dates=["timestamp"],
        )

        existing["timestamp"] = pd.to_datetime(
            existing["timestamp"],
            utc=True,
        )

        combined = pd.concat(
            [existing, new_df],
            ignore_index=True,
        )

        combined = (
            combined
            .drop_duplicates(
                "timestamp",
                keep="last",
            )
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

        combined.to_csv(
            M1_FILE,
            index=False,
        )

        # ---------------------------------------------------------
        # 6. Rebuild all derived timeframes.
        #
        # M1 data may contain the currently forming candle boundary,
        # but derived timeframes must contain COMPLETED candles only.
        # The latest completed M1 timestamp is the authoritative MT5
        # server-time boundary.
        # ---------------------------------------------------------

        completed_m1_cutoff = (
            latest_completed_timestamp
            + pd.Timedelta(minutes=1)
        )

        for name, rule in TIMEFRAME_FILES.items():
            tf = resample_ohlcv(
                combined,
                rule,
            )

            if not tf.empty:
                timeframe_minutes = {
                    "M3": 3,
                    "M5": 5,
                    "M15": 15,
                    "M30": 30,
                    "H1": 60,
                    "H4": 240,
                    "D1": 1440,
                    "W1": 10080,
                }

                minutes = timeframe_minutes.get(name)

                if minutes is not None:
                    candle_end = (
                        tf["timestamp"]
                        + pd.Timedelta(minutes=minutes)
                    )

                    tf = tf.loc[
                        candle_end <= completed_m1_cutoff
                    ].copy()

            tf.to_csv(
                DATA_DIR / f"XAUUSD_{name}.csv",
                index=False,
            )

        return {
            "status": "UPDATED",
            "previous_last_timestamp": str(last_timestamp),
            "latest_mt5_timestamp": str(
                latest_completed_timestamp
            ),
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

