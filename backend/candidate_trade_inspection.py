import pandas as pd

df = pd.read_csv("edge_outcomes_3328.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

candidates = {
    "BOS_PA_DEV":
        (df["bos"] == "PASS") &
        (df["pa_state"] == "DEVELOPING"),

    "BOS_PA_CONF":
        (df["bos"] == "PASS") &
        (df["pa_state"] == "CONFIRMING"),

    "LIQ_PA_DEV":
        (df["liquidity"] == "PASS") &
        (df["pa_state"] == "DEVELOPING"),

    "LIQ_PA_CONF":
        (df["liquidity"] == "PASS") &
        (df["pa_state"] == "CONFIRMING"),
}

for name, mask in candidates.items():

    x = df[mask].copy()

    print("\n================================================")
    print(name)
    print("================================================")

    print(
        x[
            [
                "timestamp",
                "trade_direction",
                "pa_direction",
                "pa_state",
                "bos",
                "liquidity",
                "entry",
                "stop_loss",
                "take_profit",
                "outcome",
            ]
        ].to_string(index=False)
    )

print("\n\nCandidate inspection complete.")
