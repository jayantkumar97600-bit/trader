from __future__ import annotations

import math
import pandas as pd


def backtest(df: pd.DataFrame, signal_fn, capital=10000, risk_pct=1,
             commission_bps=2, slippage=0, max_bars=5000, step=5):
    """Run a bounded, crash-safe historical simulation.

    The previous MVP called the full analysis stack on every single candle,
    which was unnecessarily expensive and could make the API connection drop.
    This version samples evaluation points, bounds the workload, and always
    returns serializable summary statistics.
    """
    if df is None or len(df) < 100:
        return {"error": "Insufficient data for backtest.", "total_trades": 0}

    work = df.tail(min(len(df), max_bars)).reset_index(drop=True)
    balance = float(capital)
    equity = [balance]
    trades = []

    start = 60
    end = len(work) - 1

    for i in range(start, end, max(1, step)):
        try:
            sig = signal_fn(work.iloc[: i + 1])
        except Exception:
            continue

        if (
            not sig
            or sig.get("status") in ("NO TRADE", "WAIT", "Insufficient data")
            or not sig.get("decision", {}).get("entry_ready", False)
        ):
            continue
        if sig.get("direction") not in ("LONG", "SHORT"):
            continue

        try:
            entry = float(sig["entry"])
            sl = float(sig["stop_loss"])
            tp = float(sig["take_profit_1"])
        except (KeyError, TypeError, ValueError):
            continue

        stop_dist = abs(entry - sl)
        if not math.isfinite(stop_dist) or stop_dist <= 0:
            continue

        risk = balance * float(risk_pct) / 100.0
        qty = risk / stop_dist
        direction = sig["direction"]

        exit_price = None
        gross_result = None
        exit_index = None

        for j in range(i + 1, min(i + 201, len(work))):
            bar = work.iloc[j]
            if direction == "LONG":
                # Conservative same-bar assumption: stop is checked first.
                if float(bar.low) <= sl:
                    exit_price = sl
                    gross_result = -risk
                    exit_index = j
                    break
                if float(bar.high) >= tp:
                    exit_price = tp
                    gross_result = risk * abs(tp - entry) / stop_dist
                    exit_index = j
                    break
            else:
                if float(bar.high) >= sl:
                    exit_price = sl
                    gross_result = -risk
                    exit_index = j
                    break
                if float(bar.low) <= tp:
                    exit_price = tp
                    gross_result = risk * abs(tp - entry) / stop_dist
                    exit_index = j
                    break

        if exit_price is None:
            continue

        fees = (abs(entry * qty) + abs(exit_price * qty)) * float(commission_bps) / 10000.0
        net_result = float(gross_result) - fees - abs(float(slippage) * qty)
        balance += net_result
        equity.append(balance)
        trades.append({
            "entry_index": i,
            "exit_index": exit_index,
            "entry": entry,
            "exit_price": float(exit_price),
            "direction": direction,
            "quantity": float(qty),
            "result": net_result,
            "balance": balance,
        })

    wins = [t for t in trades if t["result"] > 0]
    losses = [t for t in trades if t["result"] <= 0]
    gross_win = sum(t["result"] for t in wins)
    gross_loss = abs(sum(t["result"] for t in losses))

    peak = float(capital)
    max_dd = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            max_dd = max(max_dd, (peak - value) / peak)

    return {
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": len(wins) / len(trades) * 100 if trades else 0.0,
        "net_return": (balance / capital - 1) * 100 if capital else 0.0,
        "max_drawdown": max_dd * 100,
        "profit_factor": gross_win / gross_loss if gross_loss else None,
        "final_balance": balance,
        "bars_tested": len(work),
        "evaluation_step": step,
        "trades": trades,
    }
