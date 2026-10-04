import pandas as pd
import numpy as np

FILE = "bos_pa_dev_oos_2026.csv"

df = pd.read_csv(FILE)

# ---------------------------------------------------------
# FROZEN OOS DATA
# ---------------------------------------------------------

df["signal_timestamp"] = pd.to_datetime(
    df["signal_timestamp"], utc=True
)

df["execution_timestamp"] = pd.to_datetime(
    df["execution_timestamp"], utc=True
)

df["exit_timestamp"] = pd.to_datetime(
    df["exit_timestamp"], utc=True
)

# ---------------------------------------------------------
# EXECUTION COST MODEL
#
# Cost is expressed as fraction of initial 1R risk.
#
# 0.00R = current research result
# 0.05R = moderate friction
# 0.10R = high friction
# 0.15R = severe stress
#
# We deliberately do NOT claim these are exact broker costs.
# They are robustness scenarios.
# ---------------------------------------------------------

COST_SCENARIOS = {
    "BASE": 0.00,
    "MODERATE": 0.05,
    "HIGH": 0.10,
    "SEVERE": 0.15,
}

print("\n==============================================")
print("FROZEN 2026 OOS EXECUTION-COST TEST")
print("==============================================")

print(f"\nTrades: {len(df)}")
print(
    f"Period: "
    f"{df['signal_timestamp'].min()} -> "
    f"{df['signal_timestamp'].max()}"
)

# ---------------------------------------------------------
# BASIC EXECUTION DATA
# ---------------------------------------------------------

print("\n\n================ EXECUTION DATA ================\n")

df["risk_per_trade"] = abs(
    df["entry"] - df["stop_loss"]
) * df["quantity"]

df["reward_per_trade"] = abs(
    df["take_profit"] - df["entry"]
) * df["quantity"]

df["rr"] = (
    df["reward_per_trade"] /
    df["risk_per_trade"]
)

print(
    df[
        [
            "direction",
            "entry",
            "stop_loss",
            "take_profit",
            "quantity",
            "risk_per_trade",
            "reward_per_trade",
            "rr"
        ]
    ].head(10).to_string(index=False)
)

print(
    "\nRR summary:"
)

print(
    df["rr"].describe().to_string()
)

# ---------------------------------------------------------
# COST SCENARIOS
# ---------------------------------------------------------

results = []

for name, cost_r in COST_SCENARIOS.items():

    adjusted_r = df["R"].astype(float) - cost_r

    wins = adjusted_r[adjusted_r > 0]
    losses = adjusted_r[adjusted_r < 0]

    gross_profit = wins.sum()
    gross_loss = abs(losses.sum())

    pf = (
        gross_profit / gross_loss
        if gross_loss > 0
        else np.inf
    )

    results.append({
        "scenario": name,
        "cost_R": cost_r,
        "trades": len(df),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(
            len(wins) / len(df) * 100,
            2
        ),
        "net_R": round(
            adjusted_r.sum(),
            4
        ),
        "avg_R": round(
            adjusted_r.mean(),
            4
        ),
        "PF": round(
            pf,
            3
        )
    })


result_df = pd.DataFrame(results)

print("\n\n================ COST SCENARIOS ================\n")

print(
    result_df.to_string(index=False)
)

# ---------------------------------------------------------
# MAX DRAW DOWN UNDER EACH COST
# ---------------------------------------------------------

print("\n\n================ DRAWDOWN STRESS ================\n")

for name, cost_r in COST_SCENARIOS.items():

    adjusted_r = (
        df["R"].astype(float) - cost_r
    )

    equity = adjusted_r.cumsum()

    peak = equity.cummax()

    drawdown = peak - equity

    max_dd = drawdown.max()

    print(
        f"{name}: "
        f"max drawdown = {max_dd:.4f}R"
    )

# ---------------------------------------------------------
# CONSECUTIVE LOSSES
# ---------------------------------------------------------

print("\n\n================ LOSS STREAK ================\n")

for name, cost_r in COST_SCENARIOS.items():

    adjusted_r = (
        df["R"].astype(float) - cost_r
    )

    current = 0
    maximum = 0

    for r in adjusted_r:

        if r < 0:
            current += 1
            maximum = max(
                maximum,
                current
            )
        else:
            current = 0

    print(
        f"{name}: "
        f"max consecutive losses = {maximum}"
    )

# ---------------------------------------------------------
# MONTHLY COST STRESS
# ---------------------------------------------------------

print("\n\n================ MONTHLY STRESS ================\n")

for name, cost_r in COST_SCENARIOS.items():

    temp = df.copy()

    temp["adjusted_R"] = (
        temp["R"].astype(float) -
        cost_r
    )

    monthly = (
        temp.groupby("month")["adjusted_R"]
        .agg(
            trades="count",
            net_R="sum",
            avg_R="mean"
        )
        .reset_index()
    )

    print(
        f"\n--- {name} ---"
    )

    print(
        monthly.to_string(index=False)
    )

# ---------------------------------------------------------
# SAVE
# ---------------------------------------------------------

result_df.to_csv(
    "bos_pa_dev_oos_execution_cost_results.csv",
    index=False
)

print("\n\n==============================================")
print("EXECUTION-COST TEST COMPLETE")
print("==============================================")

print(
    "\nSaved:"
)

print(
    "bos_pa_dev_oos_execution_cost_results.csv"
)
