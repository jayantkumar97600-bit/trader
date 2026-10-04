import pandas as pd
import numpy as np

df = pd.read_csv("edge_outcomes_3328.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

df["year"] = df["timestamp"].dt.year

def stats(g):
    v = g[g["outcome"].isin(["TP_FIRST","SL_FIRST"])]

    if len(v) == 0:
        return pd.Series({
            "signals": len(g),
            "valid": 0,
            "tp": 0,
            "sl": 0,
            "tp_rate": np.nan,
            "expectancy_R": np.nan
        })

    tp = (v["outcome"] == "TP_FIRST").sum()
    sl = (v["outcome"] == "SL_FIRST").sum()

    return pd.Series({
        "signals": len(g),
        "valid": len(v),
        "tp": tp,
        "sl": sl,
        "tp_rate": round(tp / len(v) * 100, 2),
        "expectancy_R": round((tp * 2 - sl) / len(v), 4)
    })

conditions = {
    "ALL": pd.Series(True, index=df.index),

    "PA_DEVELOPING": (
        df["pa_state"] == "DEVELOPING"
    ),

    "PA_CONFIRMING": (
        df["pa_state"] == "CONFIRMING"
    ),

    "BOS_PASS": (
        df["bos"] == "PASS"
    ),

    "CHOCH_PASS": (
        df["choch"] == "PASS"
    ),

    "LIQUIDITY_PASS": (
        df["liquidity"] == "PASS"
    ),

    "INTERNAL_BOS_PASS": (
        df["internal_bos"] == "PASS"
    ),

    "IBOS_LIQ_PA_DEV": (
        (df["internal_bos"] == "PASS") &
        (df["liquidity"] == "PASS") &
        (df["pa_state"] == "DEVELOPING")
    ),

    "LIQ_PA_DEV": (
        (df["liquidity"] == "PASS") &
        (df["pa_state"] == "DEVELOPING")
    ),

    "LIQ_PA_CONF": (
        (df["liquidity"] == "PASS") &
        (df["pa_state"] == "CONFIRMING")
    ),

    "IBOS_LIQ_PA_CONF": (
        (df["internal_bos"] == "PASS") &
        (df["liquidity"] == "PASS") &
        (df["pa_state"] == "CONFIRMING")
    ),
}

print("\n================ YEARLY STABILITY ================\n")

for name, mask in conditions.items():

    subset = df[mask].copy()

    print(f"\n========== {name} ==========")

    if len(subset) == 0:
        print("NO DATA")
        continue

    print(
        subset.groupby("year")
        .apply(stats)
        .to_string()
    )

print("\n\n================ HALF-SPLIT ================\n")

mid = df["timestamp"].median()

print("Split date:", mid)

for name, mask in conditions.items():

    subset = df[mask].copy()

    train = subset[subset["timestamp"] <= mid]
    test = subset[subset["timestamp"] > mid]

    print(f"\n========== {name} ==========")

    print("\nTRAIN:")
    print(stats(train).to_string())

    print("\nTEST:")
    print(stats(test).to_string())

print("\n\nResearch complete.")
