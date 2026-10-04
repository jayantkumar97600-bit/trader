import pandas as pd
import numpy as np

signals = pd.read_csv("edge_outcomes_3328.csv")
signals["timestamp"] = pd.to_datetime(signals["timestamp"], utc=True)

candles = pd.read_csv("../data/mt5/XAUUSD_M15.csv")
candles["timestamp"] = pd.to_datetime(candles["timestamp"], utc=True)
candles = candles.sort_values("timestamp").reset_index(drop=True)

candidates = {
    "BOS_PA_DEV":
        (signals["bos"] == "PASS") &
        (signals["pa_state"] == "DEVELOPING"),

    "BOS_PA_CONF":
        (signals["bos"] == "PASS") &
        (signals["pa_state"] == "CONFIRMING"),

    "LIQ_PA_DEV":
        (signals["liquidity"] == "PASS") &
        (signals["pa_state"] == "DEVELOPING"),

    "LIQ_PA_CONF":
        (signals["liquidity"] == "PASS") &
        (signals["pa_state"] == "CONFIRMING"),
}

CAPITAL = 10000.0
RISK_PCT = 0.01

# Same basic cost assumptions used by the existing production backtest.
COMMISSION_RATE = 0.0
SLIPPAGE_POINTS = 0.0

def simulate(row):

    direction = row["trade_direction"]
    entry_signal = row["entry"]
    sl = row["stop_loss"]
    tp = row["take_profit"]

    if direction not in ["LONG", "SHORT"]:
        return None

    if pd.isna(entry_signal) or pd.isna(sl) or pd.isna(tp):
        return None

    # Find signal candle.
    pos = candles["timestamp"].searchsorted(row["timestamp"], side="right")

    if pos >= len(candles):
        return None

    # Production-style execution = next candle OPEN.
    execution_candle = candles.iloc[pos]
    entry = float(execution_candle["open"])

    # Apply slippage.
    if direction == "LONG":
        entry += SLIPPAGE_POINTS
    else:
        entry -= SLIPPAGE_POINTS

    risk_distance = abs(entry - sl)

    if risk_distance <= 0:
        return None

    risk_amount = CAPITAL * RISK_PCT
    quantity = risk_amount / risk_distance

    exit_price = None
    exit_reason = None
    exit_timestamp = None

    # Search forward from execution candle.
    for j in range(pos, len(candles)):

        c = candles.iloc[j]

        high = float(c["high"])
        low = float(c["low"])

        if direction == "LONG":

            sl_hit = low <= sl
            tp_hit = high >= tp

            # Conservative assumption if both are touched
            # inside the same candle: SL first.
            if sl_hit and tp_hit:
                exit_price = sl
                exit_reason = "STOP_LOSS_BOTH"
                exit_timestamp = c["timestamp"]
                break

            if sl_hit:
                exit_price = sl
                exit_reason = "STOP_LOSS"
                exit_timestamp = c["timestamp"]
                break

            if tp_hit:
                exit_price = tp
                exit_reason = "TAKE_PROFIT"
                exit_timestamp = c["timestamp"]
                break

        else:

            sl_hit = high >= sl
            tp_hit = low <= tp

            if sl_hit and tp_hit:
                exit_price = sl
                exit_reason = "STOP_LOSS_BOTH"
                exit_timestamp = c["timestamp"]
                break

            if sl_hit:
                exit_price = sl
                exit_reason = "STOP_LOSS"
                exit_timestamp = c["timestamp"]
                break

            if tp_hit:
                exit_price = tp
                exit_reason = "TAKE_PROFIT"
                exit_timestamp = c["timestamp"]
                break

    if exit_price is None:
        return None

    if direction == "LONG":
        gross = (exit_price - entry) * quantity
    else:
        gross = (entry - exit_price) * quantity

    fees = abs(entry * quantity) * COMMISSION_RATE

    net = gross - fees

    r_multiple = net / risk_amount

    return {
        "signal_timestamp": row["timestamp"],
        "execution_timestamp": execution_candle["timestamp"],
        "exit_timestamp": exit_timestamp,
        "direction": direction,
        "entry": entry,
        "stop_loss": sl,
        "take_profit": tp,
        "quantity": quantity,
        "gross_pnl": gross,
        "fees": fees,
        "net_pnl": net,
        "R": r_multiple,
        "exit_reason": exit_reason,
    }


def run_candidate(name, mask):

    subset = signals[mask].copy()
    trades = []

    for _, row in subset.iterrows():

        result = simulate(row)

        if result is not None:
            result["candidate"] = name
            trades.append(result)

    trades = pd.DataFrame(trades)

    if trades.empty:
        return None, None

    equity = CAPITAL + trades["net_pnl"].cumsum()

    peak = equity.cummax()
    drawdown = peak - equity

    wins = trades[trades["net_pnl"] > 0]
    losses = trades[trades["net_pnl"] < 0]

    gross_profit = wins["net_pnl"].sum()
    gross_loss = abs(losses["net_pnl"].sum())

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0 else np.inf
    )

    summary = {
        "candidate": name,
        "signals": len(subset),
        "executed": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(trades) * 100, 2),
        "net_profit": round(trades["net_pnl"].sum(), 2),
        "return_pct": round(
            trades["net_pnl"].sum() / CAPITAL * 100, 2
        ),
        "avg_R": round(trades["R"].mean(), 4),
        "expectancy_R": round(trades["R"].mean(), 4),
        "profit_factor": round(profit_factor, 4),
        "max_drawdown": round(drawdown.max(), 2),
        "max_drawdown_pct": round(
            drawdown.max() / CAPITAL * 100, 2
        ),
        "tp": int(
            trades["exit_reason"]
            .isin(["TAKE_PROFIT"])
            .sum()
        ),
        "sl": int(
            trades["exit_reason"]
            .isin(["STOP_LOSS", "STOP_LOSS_BOTH"])
            .sum()
        ),
    }

    return summary, trades


results = []
all_trades = []

for name, mask in candidates.items():

    summary, trades = run_candidate(name, mask)

    if summary is not None:

        results.append(summary)
        all_trades.append(trades)

summary_df = pd.DataFrame(results)

print("\n================================================")
print("PRODUCTION-STYLE CANDIDATE BACKTEST")
print("================================================\n")

print(
    summary_df
    .sort_values("net_profit", ascending=False)
    .to_string(index=False)
)

if all_trades:
    trades_df = pd.concat(all_trades, ignore_index=True)

    trades_df.to_csv(
        "candidate_production_trades.csv",
        index=False
    )

summary_df.to_csv(
    "candidate_production_results.csv",
    index=False
)

print("\nSaved:")
print("candidate_production_results.csv")
print("candidate_production_trades.csv")
