
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
            "risk_amount": float(risk),
            "r_multiple": float(gross_result / risk) if risk else 0.0,
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

    # V9 risk-adjusted performance metrics.
    net_profit = balance - float(capital)

    expectancy = (
        sum(trade["result"] for trade in trades) / len(trades)
        if trades else 0.0
    )

    average_r_multiple = (
        sum(trade["r_multiple"] for trade in trades) / len(trades)
        if trades else 0.0
    )

    max_drawdown_amount = max_dd * float(capital)

    recovery_factor = (
        net_profit / max_drawdown_amount
        if max_drawdown_amount > 0
        else None
    )

    # V11 session-wise performance analytics.
    def get_session(timestamp):
        if pd.isna(timestamp):
            return "UNKNOWN"

        hour = timestamp.hour

        if 0 <= hour < 8:
            return "ASIAN"
        if 8 <= hour < 13:
            return "LONDON"
        if 13 <= hour < 21:
            return "NEW_YORK"

        return "OTHER"

    session_stats = {
        "ASIAN": {"trades": 0, "wins": 0, "losses": 0, "net_profit": 0.0},
        "LONDON": {"trades": 0, "wins": 0, "losses": 0, "net_profit": 0.0},
        "NEW_YORK": {"trades": 0, "wins": 0, "losses": 0, "net_profit": 0.0},
        "OTHER": {"trades": 0, "wins": 0, "losses": 0, "net_profit": 0.0},
        "UNKNOWN": {"trades": 0, "wins": 0, "losses": 0, "net_profit": 0.0},
    }

    for trade in trades:
        entry_index = trade["entry_index"]
        session = "UNKNOWN"

        if "timestamp" in work.columns:
            try:
                timestamp = pd.to_datetime(
                    work.iloc[entry_index]["timestamp"],
                    utc=True,
                    errors="coerce",
                )
                session = get_session(timestamp)
            except (IndexError, KeyError, TypeError, ValueError):
                session = "UNKNOWN"

        stats = session_stats[session]
        stats["trades"] += 1
        stats["net_profit"] += float(trade["result"])

        if trade["result"] > 0:
            stats["wins"] += 1
        else:
            stats["losses"] += 1

    for stats in session_stats.values():
        stats["win_rate"] = (
            stats["wins"] / stats["trades"] * 100
            if stats["trades"] else 0.0
        )
        stats["net_profit"] = float(stats["net_profit"])
        stats["win_rate"] = float(stats["win_rate"])

    # V10 trade analytics.
    long_trades = [
        trade for trade in trades
        if trade["direction"] == "LONG"
    ]

    short_trades = [
        trade for trade in trades
        if trade["direction"] == "SHORT"
    ]

    exit_reason_breakdown = {}

    for trade in trades:
        reason = trade["exit_reason"] or "UNKNOWN"
        exit_reason_breakdown[reason] = (
            exit_reason_breakdown.get(reason, 0) + 1
        )

    trade_durations = [
        trade["exit_index"] - trade["entry_index"]
        for trade in trades
    ]

    winning_durations = [
        trade["exit_index"] - trade["entry_index"]
        for trade in trades
        if trade["result"] > 0
    ]

    losing_durations = [
        trade["exit_index"] - trade["entry_index"]
        for trade in trades
        if trade["result"] <= 0
    ]

    average_trade_duration = (
        sum(trade_durations) / len(trade_durations)
        if trade_durations else 0.0
    )

    average_winning_duration = (
        sum(winning_durations) / len(winning_durations)
        if winning_durations else 0.0
    )

    average_losing_duration = (
        sum(losing_durations) / len(losing_durations)
        if losing_durations else 0.0
    )

    average_quantity = (
        sum(trade["quantity"] for trade in trades) / len(trades)
        if trades else 0.0
    )

    long_net_profit = sum(
        trade["result"] for trade in long_trades
    )

    short_net_profit = sum(
        trade["result"] for trade in short_trades
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
        "net_profit": float(net_profit),
        "expectancy": float(expectancy),
        "average_r_multiple": float(average_r_multiple),
        "max_drawdown_amount": float(max_drawdown_amount),
        "recovery_factor": (
            float(recovery_factor)
            if recovery_factor is not None
            else None
        ),
        "trades": trades,
        "long_trades": len(long_trades),
        "short_trades": len(short_trades),
        "long_net_profit": float(long_net_profit),
        "short_net_profit": float(short_net_profit),
        "exit_reason_breakdown": exit_reason_breakdown,
        "average_trade_duration": float(average_trade_duration),
        "average_winning_duration": float(average_winning_duration),
        "average_losing_duration": float(average_losing_duration),
        "average_quantity": float(average_quantity),
        "session_stats": session_stats,
    }
