import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path


SYMBOL = "XAUUSD"

OUTPUT_DIR = Path("../data/mt5")

# Maximum bars per request
CHUNK_SIZE = 50000


print("Connecting to MT5...")

if not mt5.initialize():
    print("MT5 connection failed")
    print("Error:", mt5.last_error())
    raise SystemExit

print("MT5 connected successfully")


# -------------------------------------------------
# SYMBOL
# -------------------------------------------------

info = mt5.symbol_info(SYMBOL)

if info is None:
    print(f"{SYMBOL} not found")
    mt5.shutdown()
    raise SystemExit

if not info.visible:
    if not mt5.symbol_select(SYMBOL, True):
        print("Could not select symbol")
        mt5.shutdown()
        raise SystemExit


print()
print("Symbol:", info.name)
print("Bid:", info.bid)
print("Ask:", info.ask)
print("Point:", info.point)
print("Digits:", info.digits)
print("Tick size:", info.trade_tick_size)
print("Tick value:", info.trade_tick_value)
print("Contract size:", info.trade_contract_size)


# -------------------------------------------------
# DOWNLOAD M1 IN CHUNKS
# -------------------------------------------------

print()
print("Downloading XAUUSD M1 history...")
print("Chunk size:", CHUNK_SIZE)

all_data = []

start_pos = 0

while True:

    print(
        f"Requesting bars "
        f"{start_pos} → {start_pos + CHUNK_SIZE}"
    )

    rates = mt5.copy_rates_from_pos(
        SYMBOL,
        mt5.TIMEFRAME_M1,
        start_pos,
        CHUNK_SIZE
    )

    if rates is None:

        print("MT5 returned an error:")
        print(mt5.last_error())

        break

    if len(rates) == 0:

        print("No more data available.")
        break

    df = pd.DataFrame(rates)

    all_data.append(df)

    print(
        "Received:",
        len(df),
        "bars"
    )

    if len(df) < CHUNK_SIZE:

        print("Reached available history.")
        break

    start_pos += CHUNK_SIZE


# -------------------------------------------------
# CHECK
# -------------------------------------------------

if not all_data:

    print()
    print("NO HISTORICAL DATA RECEIVED")
    mt5.shutdown()
    raise SystemExit


# -------------------------------------------------
# COMBINE
# -------------------------------------------------

df = pd.concat(
    all_data,
    ignore_index=True
)


# -------------------------------------------------
# FORMAT
# -------------------------------------------------

df["timestamp"] = pd.to_datetime(
    df["time"],
    unit="s",
    utc=True
)

df = df.rename(
    columns={
        "tick_volume": "volume"
    }
)

df = df[
    [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]
]


df = (
    df
    .drop_duplicates("timestamp")
    .sort_values("timestamp")
    .reset_index(drop=True)
)


# -------------------------------------------------
# SAVE
# -------------------------------------------------

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

m1_file = OUTPUT_DIR / "XAUUSD_M1.csv"

df.to_csv(
    m1_file,
    index=False
)


print()
print("======================================")
print("M1 DOWNLOAD COMPLETE")
print("======================================")

print("Total candles:", len(df))
print("First:", df["timestamp"].iloc[0])
print("Last:", df["timestamp"].iloc[-1])

print()
print("Saved:")
print(m1_file)


# -------------------------------------------------
# RESAMPLE
# -------------------------------------------------

def resample_ohlcv(df, rule):

    x = df.copy()

    x = x.set_index("timestamp")

    result = x.resample(rule).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        }
    )

    result = result.dropna()

    return result.reset_index()


timeframes = {

    "M3": "3min",

    "M5": "5min",

    "M15": "15min",

    "M30": "30min",

    "H1": "1h",

    "H4": "4h",

    "D1": "1D",

    "W1": "1W"
}


print()
print("Creating timeframes...")


for name, rule in timeframes.items():

    tf = resample_ohlcv(
        df,
        rule
    )

    file = OUTPUT_DIR / f"XAUUSD_{name}.csv"

    tf.to_csv(
        file,
        index=False
    )

    print(
        name,
        "→",
        len(tf),
        "candles"
    )


mt5.shutdown()


print()
print("======================================")
print("ALL DATA READY")
print("======================================")