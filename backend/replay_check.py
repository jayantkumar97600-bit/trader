import json
import pandas as pd
from app.api.routes import make_signal, BacktestRequest

samples = json.load(open("pa_samples_age24.json"))
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

for s in samples[:5]:
    ts = pd.Timestamp(s["source_timestamp"])
    hist = df[df["timestamp"] <= ts].tail(500).copy()

    result = make_signal(hist, req)

    pa = result.get("five_minute_price_action") or result.get("price_action") or {}
    ec = result.get("entry_confirmation") or {}
    checks = ec.get("checks", {})

    print("\nTIMESTAMP:", s["source_timestamp"])
    print("STORED PA :", s["pa_direction"], s["pa_state"], s["pa_score"])
    print("REPLAY PA :", pa.get("direction"), pa.get("state"), pa.get("score"))
    print("EC STATUS :", ec.get("status"))
    print("CHECKS    :", {
        k: (v.get("status") if isinstance(v, dict) else None)
        for k, v in checks.items()
    })
