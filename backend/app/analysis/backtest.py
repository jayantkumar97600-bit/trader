
from __future__ import annotations

import math
import pandas as pd


def backtest(
    df: pd.DataFrame,
    signal_fn,
    capital=10000,
    risk_pct=1,
    commission_bps=2,
    slippage=0,
    max_bars=5000,
    step=5,
):
    """Run a bounded historical simulation with single-position control."""

    if df is None or len(df) < 100:
        return {
            "error": "Insufficient data for backtest.",
            "total_trades": 0,
        }

    work = df.tail(min(len(df), max_bars)).reset_index(drop=True)

    balance = float(capital)
    equity = [balance]
    trades = []

    start = 60
    end = len(work) - 1
    evaluation_step = max(1, int(step))

    i = start

    while i < end:
        try:
            sig = signal_fn(work.iloc[: i + 1])
        except Exception:
            i += evaluation_step
            continue

        if (
            not sig
            or sig.get("status") in (
                "NO TRADE",
                "WAIT",
                "Insufficient data",
            )
            or not sig.get("decision", {}).get("entry_ready", False)
        ):
            i += evaluation_step
            continue

        if sig.get("direction") not in ("LONG", "SHORT"):
            i += evaluation_step
            continue

        try:
            entry = float(sig["entry"])
            sl = float(sig["stop_loss"])
            tp = float(sig["take_profit_1"])
        except (KeyError, TypeError, ValueError):
            i += evaluation_step
            continue

        # Use the next candle open as the realistic execution price.
        # If the open is unavailable or invalid, retain the signal entry.
        execution_index = i + 1

        if execution_index < len(work):
            try:
                market_open = float(work.iloc[execution_index]["open"])

                if math.isfinite(market_open) and market_open > 0:
                    entry = market_open
            except (KeyError, TypeError, ValueError):
                pass

        direction = sig["direction"]

        # Validate gap execution against SL/TP levels.
        gap_exit_price = None
        gap_exit_reason = None

        if direction == "LONG":
            if entry <= sl:
                i += evaluation_step
                continue
            if entry >= tp:
                gap_exit_price = entry
                gap_exit_reason = "TAKE_PROFIT_GAP"
        else:
            if entry >= sl:
                i += evaluation_step
                continue
            if entry <= tp:
                gap_exit_price = entry
                gap_exit_reason = "TAKE_PROFIT_GAP"

        stop_dist = abs(entry - sl)

        if not math.isfinite(stop_dist) or stop_dist <= 0:
            i += evaluation_step
            continue

        risk = balance * float(risk_pct) / 100.0
        qty = risk / stop_dist
        exit_price = None
        gross_result = None
        exit_index = None
        exit_reason = None

        if gap_exit_price is not None:
            exit_price = gap_exit_price
            gross_result = risk * abs(exit_price - entry) / stop_dist
            exit_index = execution_index
            exit_reason = gap_exit_reason

        # Simulate the active position only when no gap exit occurred.
        # No new signal is evaluated until this position closes.
        if gap_exit_price is None:
            for j in range(i + 1, min(i + 201, len(work))):
                bar = work.iloc[j]

                try:
                    bar_high = float(bar["high"])
                    bar_low = float(bar["low"])
                except (KeyError, TypeError, ValueError):
                    continue

                if direction == "LONG":
                    # Conservative assumption:
                    # Stop Loss is checked before Take Profit.
                    if bar_low <= sl:
                        exit_price = sl
                        gross_result = -risk
                        exit_index = j
                        exit_reason = "STOP_LOSS"
                        break

                    if bar_high >= tp:
                        exit_price = tp
                        gross_result = (
                            risk * abs(tp - entry) / stop_dist
                        )
                        exit_index = j
                        exit_reason = "TAKE_PROFIT"
                        break

                else:
                    # Conservative assumption:
                    # Stop Loss is checked before Take Profit.
                    if bar_high >= sl:
                        exit_price = sl
                        gross_result = -risk
                        exit_index = j
                        exit_reason = "STOP_LOSS"
                        break

                    if bar_low <= tp:
                        exit_price = tp
                        gross_result = (
                            risk * abs(tp - entry) / stop_dist
                        )
                        exit_index = j
                        exit_reason = "TAKE_PROFIT"
                        break

        # If the position did not close, stop this simulation path.
        if exit_price is None or exit_index is None:
            i += evaluation_step
            continue

        fees = (
            abs(entry * qty) + abs(exit_price * qty)
        ) * float(commission_bps) / 10000.0

        slippage_cost = abs(float(slippage) * qty)

        net_result = (
            float(gross_result)
            - fees
            - slippage_cost
        )

        balance += net_result
        equity.append(balance)

        trades.append({
            "entry_index": i,
            "exit_index": exit_index,
            "entry": entry,
            "exit_price": float(exit_price),
            "direction": direction,
            "quantity": float(qty),
            "gross_result": float(gross_result),
            "fees": float(fees),
            "slippage_cost": float(slippage_cost),
            "result": float(net_result),
            "exit_reason": exit_reason,
            "balance": float(balance),
        })

        # IMPORTANT:
        # Resume evaluation only after the previous trade closes.
        i = exit_index + evaluation_step

    wins = [
        trade for trade in trades
        if trade["result"] > 0
    ]

    losses = [
        trade for trade in trades
        if trade["result"] <= 0
    ]

    gross_win = sum(
        trade["result"] for trade in wins
    )

    gross_loss = abs(sum(
        trade["result"] for trade in losses
    ))

    peak = float(capital)
    max_dd = 0.0

    for value in equity:
        peak = max(peak, value)

        if peak > 0:
            drawdown = (peak - value) / peak
            max_dd = max(max_dd, drawdown)

    # V8 risk and performance metrics.
    winning_results = [
        trade["result"] for trade in trades
        if trade["result"] > 0
    ]

    losing_results = [
        trade["result"] for trade in trades
        if trade["result"] <= 0
    ]

    average_win = (
        sum(winning_results) / len(winning_results)
        if winning_results else 0.0
    )

    average_loss = (
        sum(losing_results) / len(losing_results)
        if losing_results else 0.0
    )

    max_consecutive_wins = 0
    max_consecutive_losses = 0
    current_wins = 0
    current_losses = 0

    for trade in trades:
        if trade["result"] > 0:
            current_wins += 1
            current_losses = 0
        else:
            current_losses += 1
            current_wins = 0

        max_consecutive_wins = max(
            max_consecutive_wins, current_wins
        )
        max_consecutive_losses = max(
            max_consecutive_losses, current_losses
        )

    return {
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": (
            len(wins) / len(trades) * 100
            if trades
            else 0.0
        ),
        "net_return": (
            (balance / capital - 1) * 100
            if capital
            else 0.0
        ),
        "max_drawdown": max_dd * 100,
        "profit_factor": (
            gross_win / gross_loss
            if gross_loss
            else None
        ),
        "final_balance": float(balance),
        "bars_tested": len(work),
        "evaluation_step": evaluation_step,
        "equity_curve": equity,
        "average_win": float(average_win),
        "average_loss": float(average_loss),
        "max_consecutive_wins": max_consecutive_wins,
        "max_consecutive_losses": max_consecutive_losses,
        "trades": trades,
    }
