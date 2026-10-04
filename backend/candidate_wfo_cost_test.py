import pandas as pd
import numpy as np

df = pd.read_csv("candidate_production_trades.csv")

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
# COST SENSITIVITY
# ---------------------------------------------------------
# We model additional cost as a fraction of risk per trade.
# 0.00R = no additional cost
# 0.05R = 5% of the planned 1R risk
# 0.10R = 10%
# 0.15R = 15%
# 0.20R = 20%
#
# This is deliberately a stress test rather than pretending
# we know the exact broker spread/commission for every period.
# ---------------------------------------------------------

COSTS_R = [
    0.00,
    0.05,
    0.10,
    0.15,
    0.20,
]

print("\n================================================")
print("WALK-FORWARD + COST SENSITIVITY")
print("================================================")


def metrics(x, r_col="R"):

    if len(x) == 0:
        return None

    wins = x[x[r_col] > 0]
    losses = x[x[r_col] < 0]

    gp = wins[r_col].sum()
    gl = abs(losses[r_col].sum())

    pf = gp / gl if gl > 0 else np.inf

    return {
        "trades": len(x),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(x) * 100, 2),
        "net_R": round(x[r_col].sum(), 4),
        "avg_R": round(x[r_col].mean(), 4),
        "PF": round(pf, 3),
    }


# =========================================================
# 1. COST SENSITIVITY
# =========================================================

print("\n\n================ COST SENSITIVITY ================\n")

cost_rows = []

for candidate, x in df.groupby("candidate"):

    for cost in COSTS_R:

        y = x.copy()

        # Apply cost to every executed trade.
        y["net_R_cost"] = y["R"] - cost

        s = metrics(y, "net_R_cost")

        cost_rows.append({
            "candidate": candidate,
            "cost_R_per_trade": cost,
            **s
        })

cost_df = pd.DataFrame(cost_rows)

print(
    cost_df.to_string(index=False)
)

cost_df.to_csv(
    "candidate_cost_sensitivity.csv",
    index=False
)


# =========================================================
# 2. ROLLING WALK-FORWARD
# =========================================================
#
# We divide the chronological history into 5 sequential
# test windows.
#
# No random shuffling.
#
# The purpose here is NOT to optimize each window.
# It is to see whether the already-defined candidate survives
# across genuinely different future periods.
# =========================================================

print("\n\n================ 5-WINDOW WALK-FORWARD ================\n")

wfo_rows = []

for candidate, x in df.groupby("candidate"):

    x = (
        x.sort_values("signal_timestamp")
        .reset_index(drop=True)
        .copy()
    )

    chunks = np.array_split(x, 5)

    print(f"\n--- {candidate} ---")

    for i, chunk in enumerate(chunks, 1):

        s = metrics(chunk)

        start = chunk["signal_timestamp"].min()
        end = chunk["signal_timestamp"].max()

        row = {
            "candidate": candidate,
            "window": i,
            "start": start,
            "end": end,
            **s
        }

        wfo_rows.append(row)

        print(
            f"WINDOW {i}: "
            f"{start.date()} -> {end.date()} | "
            f"trades={s['trades']} | "
            f"win={s['win_rate']}% | "
            f"netR={s['net_R']} | "
            f"avgR={s['avg_R']} | "
            f"PF={s['PF']}"
        )


wfo_df = pd.DataFrame(wfo_rows)

wfo_df.to_csv(
    "candidate_walk_forward.csv",
    index=False
)


# =========================================================
# 3. WALK-FORWARD COST STRESS
# =========================================================

print("\n\n================ WALK-FORWARD COST STRESS ================\n")

stress_rows = []

for candidate, x in df.groupby("candidate"):

    x = (
        x.sort_values("signal_timestamp")
        .reset_index(drop=True)
        .copy()
    )

    chunks = np.array_split(x, 5)

    print(f"\n--- {candidate} ---")

    for i, chunk in enumerate(chunks, 1):

        line = []

        for cost in COSTS_R:

            adjusted_R = chunk["R"] - cost

            net_R = adjusted_R.sum()

            wins = adjusted_R[adjusted_R > 0]
            losses = adjusted_R[adjusted_R < 0]

            gp = wins.sum()
            gl = abs(losses.sum())

            pf = gp / gl if gl > 0 else np.inf

            stress_rows.append({
                "candidate": candidate,
                "window": i,
                "cost_R": cost,
                "trades": len(chunk),
                "net_R": round(net_R, 4),
                "avg_R": round(adjusted_R.mean(), 4),
                "PF": round(pf, 3),
            })

            line.append(
                f"{cost:.2f}R:{net_R:.2f}R"
            )

        print(
            f"WINDOW {i}: " +
            " | ".join(line)
        )


stress_df = pd.DataFrame(stress_rows)

stress_df.to_csv(
    "candidate_wfo_cost_stress.csv",
    index=False
)


# =========================================================
# 4. SURVIVAL SCORE
# =========================================================

print("\n\n================ SURVIVAL SUMMARY ================\n")

for candidate, x in wfo_df.groupby("candidate"):

    positive_windows = int((x["net_R"] > 0).sum())
    positive_pf = int((x["PF"] > 1).sum())

    print(
        f"{candidate}: "
        f"{positive_windows}/5 positive windows | "
        f"{positive_pf}/5 windows PF>1"
    )


# =========================================================
# 5. COST BREAK-EVEN
# =========================================================

print("\n\n================ COST BREAK-EVEN ================\n")

for candidate, x in df.groupby("candidate"):

    avg_r = x["R"].mean()

    print(
        f"{candidate}: "
        f"raw expectancy = {avg_r:.4f}R | "
        f"theoretical cost tolerance = {avg_r:.4f}R/trade"
    )


print("\n\n================================================")
print("WALK-FORWARD + COST TEST COMPLETE")
print("================================================")

print("\nSaved:")
print("candidate_cost_sensitivity.csv")
print("candidate_walk_forward.csv")
print("candidate_wfo_cost_stress.csv")
