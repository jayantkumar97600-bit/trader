import MetaTrader5 as mt5
import pandas as pd

SYMBOL = "XAUUSD"

print("Connecting...")

if not mt5.initialize():
    print("MT5 connection failed")
    print(mt5.last_error())
    raise SystemExit

print("Connected")

info = mt5.symbol_info(SYMBOL)

print("Symbol:", info.name)
print("Visible:", info.visible)

if not info.visible:
    print("Selecting symbol...")
    mt5.symbol_select(SYMBOL, True)

print()
print("Requesting only 1000 M1 candles...")

rates = mt5.copy_rates_from_pos(
    SYMBOL,
    mt5.TIMEFRAME_M1,
    0,
    1000
)

print()
print("Result:", rates)

if rates is None:
    print("ERROR:")
    print(mt5.last_error())
else:
    print()
    print("SUCCESS")
    print("Number of candles:", len(rates))

    df = pd.DataFrame(rates)

    df["time"] = pd.to_datetime(
        df["time"],
        unit="s",
        utc=True
    )

    print()
    print(df.head())
    print()
    print(df.tail())

mt5.shutdown()