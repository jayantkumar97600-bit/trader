import json
import pandas as pd

SAMPLES = "pa_samples_age24.json"
CSV = r"..\data\mt5\XAUUSD_M15.csv"

samples = json.load(open(SAMPLES, encoding="utf-8"))

df = pd.read_csv(CSV)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

print("M15 candles:", len(df))
print("PA samples:", len(samples))
print("CSV range:", df["timestamp"].iloc[0], "->", df["timestamp"].iloc[-1])
print("Sample range:", samples[0]["source_timestamp"], "->", samples[-1]["source_timestamp"])

for s in samples[:3]:
    print(
        s["source_timestamp"],
        s["trade_direction"],
        s["signal_entry"],
        s["signal_stop_loss"],
        s["signal_take_profit"],
    )
