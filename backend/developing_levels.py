import json
import pandas as pd
from app.api.routes import make_signal, BacktestRequest

samples = json.load(open("pa_samples_age24.json"))
targets = pd.read_csv("developing_target_samples.csv")
target_ts = set(targets["timestamp"].astype(str))

df = pd.read_csv("../data/mt5/XAUUSD_M15.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

req = BacktestRequest(
    asset="XAUUSD",
    csv_path="mt5/XAUUSD_M15.csv",
    capital=10000,
    risk_pct=1,
    min_rr=2,
    timeframe="15m",
    htf_timeframe="1h",
    hierarchy=["4h","1h","15m","5m"],
)

rows = []

for s in samples:
    if s["source_timestamp"] not in target_ts:
        continue

    ts = pd.Timestamp(s["source_timestamp"])
    hist = df[df["timestamp"] <= ts].tail(500).copy()

    result = make_signal(hist, req)

    pa = result.get("five_minute_price_action") or result.get("price_action") or {}
    ec = result.get("entry_confirmation") or {}

    rows.append({
        "timestamp": s["source_timestamp"],
        "trade_direction": s["trade_direction"],
        "pa_direction": s["pa_direction"],
        "pa_state": s["pa_state"],
        "pa_score": s["pa_score"],
        "entry": result.get("entry"),
        "stop_loss": result.get("stop_loss"),
        "take_profit": result.get("take_profit_1"),
        "rr": result.get("rr"),
        "ec_status": ec.get("status"),
    })

out = pd.DataFrame(rows)

print("\n=== TARGET LEVELS ===")
print(out.to_string(index=False))

out.to_csv("developing_target_levels.csv", index=False)
print("\nSaved: developing_target_levels.csv")
