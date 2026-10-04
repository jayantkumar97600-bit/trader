import pandas as pd
import numpy as np

TRADES_FILE = "candidate_production_trades.csv"

df = pd.read_csv(TRADES_FILE)
df["signal_timestamp"] = pd.to_datetime(
    df["signal_timestamp"], utc=True
)

# =========================================================
# FROZEN RULE
# =========================================================
# BOS PASS + PA DEVELOPING
#
# This rule is NOT optimized on the OOS period.
# =========================================================

candidate = "BOS_PA_DEV"

x = df[df["candidate"] == candidate].copy()

# Development period:
# 2024-08 through 2025-12-31
#
# OOS period:
# 2026-01-01 onward

development = x[
    x["signal_timestamp"] < "2026-01-01"
].copy()

oos = x[
    x["signal_timestamp"] >= "2026-01-01"
].copy()


def metrics(data):

    if len(data) == 0:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "net_R": 0,
            "avg_R": 0,
            "PF": 0,
            "max_consecutive_losses": 0
        }

    r = data["R"].astype(float)

    wins = r[r > 0]
    losses = r[r < 0]

    gross_profit = wins.sum()
    gross_loss = abs(losses.sum())

    pf = (
        gross_profit / gross_loss
        if gross_loss > 0
        else np.inf
    )

    # Consecutive losses
    max_loss_streak = 0
    current = 0

    for value in r:
        if value < 0:
            current += 1
            max_loss_streak = max(
                max_loss_streak,
                current
            )
        else:
            current = 0

    return {
        "trades": len(data),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(
            len(wins) / len(data) * 100,
            2
        ),
        "net_R": round(r.sum(), 4),
        "avg_R": round(r.mean(), 4),
        "PF": round(pf, 3),
        "max_consecutive_losses": max_loss_streak
    }


print("\n==============================================")
print("FROZEN RULE OOS VALIDATION")
print("==============================================")

print("\nRULE:")
print("BOS PASS + PA DEVELOPING")

print("\nDEVELOPMENT:")
print(
    development["signal_timestamp"].min(),
    "->",
    development["signal_timestamp"].max()
)

print("\nOOS:")
print(
    oos["signal_timestamp"].min(),
    "->",
    oos["signal_timestamp"].max()
)


# =========================================================
# DEVELOPMENT RESULT
# =========================================================

dev_m = metrics(development)

print("\n\n================ DEVELOPMENT ================\n")

for k, v in dev_m.items():
    print(f"{k}: {v}")


# =========================================================
# OOS RESULT
# =========================================================

oos_m = metrics(oos)

print("\n\n================ UNTOUCHED OOS ================\n")

for k, v in oos_m.items():
    print(f"{k}: {v}")


# =========================================================
# OOS YEARLY BREAKDOWN
# =========================================================

print("\n\n================ OOS YEAR BREAKDOWN ================\n")

if len(oos):

    oos["year"] = (
        oos["signal_timestamp"]
        .dt.year
    )

    for year, group in oos.groupby("year"):

        m = metrics(group)

        print(
            f"{year}: "
            f"trades={m['trades']} | "
            f"win={m['win_rate']}% | "
            f"netR={m['net_R']} | "
            f"avgR={m['avg_R']} | "
            f"PF={m['PF']} | "
            f"maxL={m['max_consecutive_losses']}"
        )


# =========================================================
# OOS DIRECTION
# =========================================================

print("\n\n================ OOS DIRECTION ================\n")

if len(oos):

    for direction, group in oos.groupby("direction"):

        m = metrics(group)

        print(
            f"{direction}: "
            f"trades={m['trades']} | "
            f"win={m['win_rate']}% | "
            f"netR={m['net_R']} | "
            f"PF={m['PF']}"
        )


# =========================================================
# OOS SESSION
# =========================================================

print("\n\n================ OOS SESSION ================\n")


def session(hour):

    if 0 <= hour < 8:
        return "Asian"
    elif 8 <= hour < 13:
        return "London"
    elif 13 <= hour < 21:
        return "New York"
    return "Other"


if len(oos):

    oos["session"] = (
        oos["signal_timestamp"]
        .dt.hour
        .apply(session)
    )

    for sess, group in oos.groupby("session"):

        m = metrics(group)

        print(
            f"{sess}: "
            f"trades={m['trades']} | "
            f"win={m['win_rate']}% | "
            f"netR={m['net_R']} | "
            f"PF={m['PF']}"
        )


# =========================================================
# OOS COST STRESS
# =========================================================

print("\n\n================ OOS COST STRESS ================\n")

for cost in [0.00, 0.05, 0.10, 0.15, 0.20]:

    if len(oos):

        adjusted = (
            oos["R"].astype(float) - cost
        )

        gp = adjusted[adjusted > 0].sum()
        gl = abs(
            adjusted[adjusted < 0].sum()
        )

        pf = (
            gp / gl
            if gl > 0
            else np.inf
        )

        print(
            f"cost={cost:.2f}R | "
            f"netR={adjusted.sum():.4f} | "
            f"avgR={adjusted.mean():.4f} | "
            f"PF={pf:.3f}"
        )


# =========================================================
# OOS MONTHLY
# =========================================================

print("\n\n================ OOS MONTHLY ================\n")

if len(oos):

    oos["month"] = (
        oos["signal_timestamp"]
        .dt.to_period("M")
        .astype(str)
    )

    monthly = (
        oos.groupby("month")["R"]
        .agg(
            trades="count",
            net_R="sum",
            avg_R="mean"
        )
        .reset_index()
    )

    print(
        monthly.to_string(index=False)
    )


# =========================================================
# SAVE
# =========================================================

development.to_csv(
    "bos_pa_dev_development.csv",
    index=False
)

oos.to_csv(
    "bos_pa_dev_oos_2026.csv",
    index=False
)

print("\n\n==============================================")
print("OOS TEST COMPLETE")
print("==============================================")

print("\nSaved:")
print("bos_pa_dev_development.csv")
print("bos_pa_dev_oos_2026.csv")
