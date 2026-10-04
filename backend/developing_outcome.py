import pandas as pd

df = pd.read_csv("../data/mt5/XAUUSD_M15.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

s = pd.read_csv("developing_target_levels.csv")
s["timestamp"] = pd.to_datetime(s["timestamp"], utc=True)

outcomes = []

for _, row in s.iterrows():
    future = df[df["timestamp"] > row["timestamp"]].reset_index(drop=True)
    direction = row["trade_direction"]
    entry = float(row["entry"])
    sl = float(row["stop_loss"])
    tp = float(row["take_profit"])

    entry_i = None

    for i, c in future.iterrows():
        entry_hit = (
            c["high"] >= entry if direction == "LONG"
            else c["low"] <= entry
        )

        if entry_hit:
            entry_i = i
            break

    if entry_i is None:
        outcomes.append("NO_ENTRY")
        continue

    outcome = "NO_EXIT"

    for _, c in future.iloc[entry_i:].iterrows():
        hit_sl = (
            c["low"] <= sl if direction == "LONG"
            else c["high"] >= sl
        )

        hit_tp = (
            c["high"] >= tp if direction == "LONG"
            else c["low"] <= tp
        )

        if hit_sl and hit_tp:
            outcome = "BOTH_SAME_CANDLE"
            break
        elif hit_sl:
            outcome = "SL_FIRST"
            break
        elif hit_tp:
            outcome = "TP_FIRST"
            break

    outcomes.append(outcome)

s["outcome"] = outcomes

s["pa_relation"] = s.apply(
    lambda r: "MATCH"
    if (
        (r["trade_direction"] == "LONG" and r["pa_direction"] == "BULLISH")
        or
        (r["trade_direction"] == "SHORT" and r["pa_direction"] == "BEARISH")
    )
    else "OPPOSITE",
    axis=1,
)

print("\n=== TARGET OUTCOMES ===")
print(s["outcome"].value_counts())

print("\n=== BY PA RELATION ===")
print(pd.crosstab(s["pa_relation"], s["outcome"]))

print("\n=== BY PA SCORE ===")
print(
    s.groupby("pa_score")["outcome"]
    .value_counts()
    .unstack(fill_value=0)
)

print("\n=== ALL 16 ===")
print(
    s[
        [
            "timestamp",
            "trade_direction",
            "pa_direction",
            "pa_score",
            "entry",
            "stop_loss",
            "take_profit",
            "ec_status",
            "outcome",
        ]
    ].to_string(index=False)
)

s.to_csv("developing_target_outcomes.csv", index=False)
print("\nSaved: developing_target_outcomes.csv")
