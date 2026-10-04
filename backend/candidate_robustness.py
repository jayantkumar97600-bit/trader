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

df["year"] = df["signal_timestamp"].dt.year
df["month"] = df["signal_timestamp"].dt.to_period("M").astype(str)
df["hour_utc"] = df["signal_timestamp"].dt.hour

def session(hour):
    if 0 <= hour < 8:
        return "ASIAN"
    elif 8 <= hour < 13:
        return "LONDON"
    elif 13 <= hour < 21:
        return "NEW_YORK"
    return "OTHER"

df["session"] = df["hour_utc"].apply(session)

df["holding_minutes"] = (
    df["exit_timestamp"] - df["execution_timestamp"]
).dt.total_seconds() / 60

df["win"] = df["net_pnl"] > 0


def stats(x):

    if len(x) == 0:
        return None

    wins = x[x["net_pnl"] > 0]
    losses = x[x["net_pnl"] < 0]

    gp = wins["net_pnl"].sum()
    gl = abs(losses["net_pnl"].sum())

    pf = gp / gl if gl > 0 else np.inf

    return {
        "trades": len(x),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(x) * 100, 2),
        "net_pnl": round(x["net_pnl"].sum(), 2),
        "avg_R": round(x["R"].mean(), 4),
        "PF": round(pf, 3),
        "avg_hold_min": round(x["holding_minutes"].mean(), 1),
    }


print("\n================================================")
print("ROBUSTNESS TEST")
print("================================================")


# =================================================
# 1. YEAR-WISE
# =================================================

print("\n\n================ YEAR-WISE ================\n")

for candidate, x in df.groupby("candidate"):

    print(f"\n--- {candidate} ---")

    rows = []

    for year, y in x.groupby("year"):
        s = stats(y)
        s["year"] = year
        rows.append(s)

    print(
        pd.DataFrame(rows)
        .sort_values("year")
        .to_string(index=False)
    )


# =================================================
# 2. LONG VS SHORT
# =================================================

print("\n\n================ DIRECTION ================\n")

for candidate, x in df.groupby("candidate"):

    print(f"\n--- {candidate} ---")

    rows = []

    for direction, y in x.groupby("direction"):
        s = stats(y)
        s["direction"] = direction
        rows.append(s)

    print(
        pd.DataFrame(rows)
        .to_string(index=False)
    )


# =================================================
# 3. SESSION
# =================================================

print("\n\n================ SESSION ================\n")

for candidate, x in df.groupby("candidate"):

    print(f"\n--- {candidate} ---")

    rows = []

    for sess, y in x.groupby("session"):

        s = stats(y)
        s["session"] = sess
        rows.append(s)

    print(
        pd.DataFrame(rows)
        .sort_values("session")
        .to_string(index=False)
    )


# =================================================
# 4. MONTHLY
# =================================================

print("\n\n================ MONTHLY ================\n")

monthly_rows = []

for candidate, x in df.groupby("candidate"):

    for month, y in x.groupby("month"):

        s = stats(y)

        monthly_rows.append({
            "candidate": candidate,
            "month": month,
            **s
        })

monthly = pd.DataFrame(monthly_rows)

print(
    monthly
    .sort_values(["candidate", "month"])
    .to_string(index=False)
)

monthly.to_csv(
    "candidate_monthly_robustness.csv",
    index=False
)


# =================================================
# 5. MAX CONSECUTIVE LOSSES
# =================================================

print("\n\n================ LOSING STREAK ================\n")

for candidate, x in df.groupby("candidate"):

    x = x.sort_values("execution_timestamp")

    streak = 0
    max_streak = 0

    for pnl in x["net_pnl"]:

        if pnl < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0

    print(
        f"{candidate}: "
        f"max consecutive losses = {max_streak}"
    )


# =================================================
# 6. CHRONOLOGICAL HALF SPLIT
# =================================================

print("\n\n================ CHRONOLOGICAL OOS SPLIT ================\n")

for candidate, x in df.groupby("candidate"):

    x = x.sort_values("signal_timestamp").reset_index(drop=True)

    midpoint = len(x) // 2

    train = x.iloc[:midpoint]
    test = x.iloc[midpoint:]

    a = stats(train)
    b = stats(test)

    print(f"\n--- {candidate} ---")

    print(
        "FIRST HALF :",
        a
    )

    print(
        "SECOND HALF:",
        b
    )


# =================================================
# 7. 3-WAY CHRONOLOGICAL SPLIT
# =================================================

print("\n\n================ 3-WAY CHRONOLOGICAL SPLIT ================\n")

for candidate, x in df.groupby("candidate"):

    x = x.sort_values("signal_timestamp").reset_index(drop=True)

    chunks = np.array_split(x, 3)

    print(f"\n--- {candidate} ---")

    for i, chunk in enumerate(chunks, 1):

        s = stats(chunk)

        print(
            f"PART {i}: "
            f"trades={s['trades']} "
            f"win={s['win_rate']}% "
            f"net={s['net_pnl']} "
            f"avgR={s['avg_R']} "
            f"PF={s['PF']}"
        )


# =================================================
# 8. WORST LOSING PERIODS
# =================================================

print("\n\n================ WORST MONTHS ================\n")

for candidate, x in df.groupby("candidate"):

    monthly_pnl = (
        x.groupby("month")["net_pnl"]
        .sum()
        .sort_values()
    )

    print(f"\n--- {candidate} ---")
    print(monthly_pnl.head(5).to_string())


# =================================================
# 9. BEST MONTHS
# =================================================

print("\n\n================ BEST MONTHS ================\n")

for candidate, x in df.groupby("candidate"):

    monthly_pnl = (
        x.groupby("month")["net_pnl"]
        .sum()
        .sort_values(ascending=False)
    )

    print(f"\n--- {candidate} ---")
    print(monthly_pnl.head(5).to_string())


print("\n\n================================================")
print("ROBUSTNESS TEST COMPLETE")
print("================================================")

print("\nSaved:")
print("candidate_monthly_robustness.csv")
