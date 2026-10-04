
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

    # V14.1 diagnostic counters.
    diagnostics = {
        "signal_evaluations": 0,
        "signal_exceptions": 0,
        "status_rejected": 0,
        "entry_not_ready": 0,
        "invalid_direction": 0,
        "invalid_levels": 0,
        "invalid_stop_distance": 0,
        "executed_trades": 0,
        "executed_trade_traces": [],
        "signal_statuses": {},
        "status_reasons": {},
        "signal_directions": {},
        "decision_states": {},
        "entry_ready": 0,
        "execution_rejections": {},
        "executed_directions": {"LONG": 0, "SHORT": 0},
        "gate_failures": {},
        "failed_gate_combinations": {},
        "passed_gate_counts": {},
        "entry_confirmation_statuses": {},
        "entry_confirmation_reasons": {},
        "entry_check_statuses": {},
        "price_action_failures": {},
        "price_action_profile": {
            "directions": {},
            "states": {},
            "score_bands": {},
            "direction_matches_trade": 0,
            "direction_opposite_trade": 0,
            "direction_neutral_trade": 0,
            "direction_conflicts_trade": 0,
        },
        "price_action_samples": [],
        "near_miss_samples": [],
        "rejection_details": [],
    }

    start = 60
    end = len(work) - 1
    evaluation_step = max(1, int(step))

    i = start

    while i < end:
        diagnostics["signal_evaluations"] += 1

        try:
            sig = signal_fn(work.iloc[: i + 1])
        except Exception:
            diagnostics["signal_exceptions"] += 1
            i += evaluation_step
            continue

        if not sig:
            diagnostics["status_rejected"] += 1
            diagnostics["signal_statuses"]["EMPTY_SIGNAL"] = (
                diagnostics["signal_statuses"].get("EMPTY_SIGNAL", 0) + 1
            )
            i += evaluation_step
            continue

        status = sig.get("status", "MISSING_STATUS")
        diagnostics["signal_statuses"][status] = (
            diagnostics["signal_statuses"].get(status, 0) + 1
        )

        reason = sig.get("reason")
        if reason:
            diagnostics["status_reasons"][reason] = (
                diagnostics["status_reasons"].get(reason, 0) + 1
            )

        signal_direction = sig.get("direction", "NEUTRAL")
        diagnostics["signal_directions"][signal_direction] = (
            diagnostics["signal_directions"].get(signal_direction, 0) + 1
        )

        decision_state = sig.get("decision", {}).get(
            "decision",
            "MISSING_DECISION",
        )
        diagnostics["decision_states"][decision_state] = (
            diagnostics["decision_states"].get(decision_state, 0) + 1
        )

        pa_result = (
            sig.get("five_minute_price_action")
            or sig.get("price_action")
            or {}
        )

        pa_direction = pa_result.get("direction", "MISSING")
        pa_state = pa_result.get("state", "MISSING")
        pa_score = pa_result.get("score")
        pa_profile = diagnostics["price_action_profile"]
        pa_profile["directions"][pa_direction] = (
            pa_profile["directions"].get(pa_direction, 0) + 1
        )
        pa_profile["states"][pa_state] = (
            pa_profile["states"].get(pa_state, 0) + 1
        )

        try:
            pa_score_value = float(pa_score)
        except (TypeError, ValueError):
            pa_score_value = None

        if pa_score_value is None:
            score_band = "MISSING"
        elif pa_score_value < 20:
            score_band = "0-19"
        elif pa_score_value < 40:
            score_band = "20-39"
        elif pa_score_value < 65:
            score_band = "40-64"
        else:
            score_band = "65-100"

        pa_profile["score_bands"][score_band] = (
            pa_profile["score_bands"].get(score_band, 0) + 1
        )

        expected_pa_direction = (
            "BULLISH" if signal_direction == "LONG" else "BEARISH"
        )
        if pa_direction == expected_pa_direction:
            pa_profile["direction_matches_trade"] += 1
        elif pa_direction == "NEUTRAL":
            pa_profile["direction_neutral_trade"] += 1
        else:
            pa_profile["direction_opposite_trade"] += 1

        if pa_direction != expected_pa_direction:
            pa_profile["direction_conflicts_trade"] += 1

        if len(diagnostics["price_action_samples"]) < 5000:
            diagnostics["price_action_samples"].append({
                "source_timestamp": sig.get("historical_mtf_context", {}).get(
                    "source_timestamp"
                ),
                "evaluation_timestamp": pa_result.get("current_candle", {}).get(
                    "timestamp"
                ),
                "mtf_context": sig.get("historical_mtf_context", {}),
                "trade_direction": sig.get("direction"),
                "signal_entry": sig.get("entry"),
                "signal_stop_loss": sig.get("stop_loss"),
                "signal_take_profit": sig.get("take_profit_1"),
                "pa_direction": pa_result.get("direction"),
                "pa_state": pa_result.get("state"),
                "pa_score": pa_result.get("score"),
                "momentum": pa_result.get("momentum"),
                "rejection": pa_result.get("rejection"),
                "engulfing": pa_result.get("engulfing"),
                "breakout": pa_result.get("breakout"),
                "structure_context": pa_result.get("structure_context"),
                "sr_context": pa_result.get("sr_context"),
            })

        if status in (
            "NO TRADE",
            "WAIT",
            "Insufficient data",
        ):
            diagnostics["status_rejected"] += 1
            i += evaluation_step
            continue

        if not sig.get("decision", {}).get("entry_ready", False):
            diagnostics["entry_not_ready"] += 1

            decision = sig.get("decision", {})
            failed_gates = decision.get("failed_gates", [])

            for gate in failed_gates:
                diagnostics["gate_failures"][gate] = (
                    diagnostics["gate_failures"].get(gate, 0) + 1
                )

            failed_combination = " + ".join(sorted(failed_gates)) or "NONE"
            diagnostics["failed_gate_combinations"][failed_combination] = (
                diagnostics["failed_gate_combinations"].get(
                    failed_combination,
                    0,
                ) + 1
            )

            passed_count = decision.get("passed_count", 0)
            diagnostics["passed_gate_counts"][passed_count] = (
                diagnostics["passed_gate_counts"].get(passed_count, 0) + 1
            )

            confirmation_status = sig.get("entry_confirmation", {}).get(
                "status",
                "MISSING",
            )
            diagnostics["entry_confirmation_statuses"][confirmation_status] = (
                diagnostics["entry_confirmation_statuses"].get(
                    confirmation_status,
                    0,
                ) + 1
            )

            confirmation_reason = sig.get("entry_confirmation", {}).get(
                "reason",
                "MISSING",
            )
            diagnostics["entry_confirmation_reasons"][confirmation_reason] = (
                diagnostics["entry_confirmation_reasons"].get(
                    confirmation_reason,
                    0,
                ) + 1
            )

            confirmation_checks = sig.get("entry_confirmation", {}).get(
                "checks",
                {},
            )
            for name, check in confirmation_checks.items():
                check_status = check.get("status", "MISSING")
                by_status = diagnostics["entry_check_statuses"].setdefault(
                    name,
                    {},
                )
                by_status[check_status] = by_status.get(check_status, 0) + 1

            diagnostics["near_miss_samples"].append({
                "source_timestamp": sig.get("historical_mtf_context", {}).get(
                    "source_timestamp"
                ),
                "direction": sig.get("direction"),
                "evaluation_index": i,
                "signal_entry": sig.get("entry"),
                "signal_stop_loss": sig.get("stop_loss"),
                "signal_take_profit": sig.get("take_profit_1"),
                "passed_gate_count": passed_count,
                "failed_gates": failed_gates,
                "passed_gates": decision.get("passed_gates", []),
                "entry_confirmation_status": confirmation_status,
                "entry_confirmation_reason": sig.get(
                    "entry_confirmation",
                    {},
                ).get("reason"),
                "checks": {
                    name: {
                        "status": check.get("status"),
                        "reason": check.get("reason"),
                    }
                    for name, check in confirmation_checks.items()
                },
            })

            pa_reason = (
                sig.get("entry_confirmation", {})
                .get("checks", {})
                .get("price_action", {})
                .get("reason", "UNKNOWN")
            )

            diagnostics["price_action_failures"][pa_reason] = (
                diagnostics["price_action_failures"].get(pa_reason, 0) + 1
            )

            diagnostics["rejection_details"].append(
                {
                    "status": sig.get("status"),
                    "direction": sig.get("direction"),
                "evaluation_index": i,
                "signal_entry": sig.get("entry"),
                "signal_stop_loss": sig.get("stop_loss"),
                "signal_take_profit": sig.get("take_profit_1"),
                    "decision": sig.get("decision"),
                }
            )

            i += evaluation_step
            continue

        diagnostics["entry_ready"] += 1

        if sig.get("direction") not in ("LONG", "SHORT"):
            diagnostics["invalid_direction"] += 1
            diagnostics["execution_rejections"]["INVALID_DIRECTION"] = (
                diagnostics["execution_rejections"].get("INVALID_DIRECTION", 0) + 1
            )
            i += evaluation_step
            continue

        try:
            entry = float(sig["entry"])
            sl = float(sig["stop_loss"])
            tp = float(sig["take_profit_1"])
        except (KeyError, TypeError, ValueError):
            diagnostics["invalid_levels"] += 1
            diagnostics["execution_rejections"]["INVALID_LEVELS"] = (
                diagnostics["execution_rejections"].get("INVALID_LEVELS", 0) + 1
            )
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
                diagnostics["execution_rejections"]["GAP_BEYOND_STOP"] = (
                    diagnostics["execution_rejections"].get("GAP_BEYOND_STOP", 0) + 1
                )
                i += evaluation_step
                continue
            if entry >= tp:
                gap_exit_price = entry
                gap_exit_reason = "TAKE_PROFIT_GAP"
        else:
            if entry >= sl:
                diagnostics["execution_rejections"]["GAP_BEYOND_STOP"] = (
                    diagnostics["execution_rejections"].get("GAP_BEYOND_STOP", 0) + 1
                )
                i += evaluation_step
                continue
            if entry <= tp:
                gap_exit_price = entry
                gap_exit_reason = "TAKE_PROFIT_GAP"

        stop_dist = abs(entry - sl)

        if not math.isfinite(stop_dist) or stop_dist <= 0:
            diagnostics["invalid_stop_distance"] += 1
            diagnostics["execution_rejections"]["INVALID_STOP_DISTANCE"] = (
                diagnostics["execution_rejections"].get("INVALID_STOP_DISTANCE", 0) + 1
            )
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
            diagnostics["execution_rejections"]["UNRESOLVED_POSITION"] = (
                diagnostics["execution_rejections"].get("UNRESOLVED_POSITION", 0) + 1
            )
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
        diagnostics["executed_trades"] += 1
        if len(diagnostics["executed_trade_traces"]) < 100:
            diagnostics["executed_trade_traces"].append({
                "entry_index": i,
                "direction": direction,
                "signal_entry": sig.get("entry"),
                "signal_stop_loss": sig.get("stop_loss"),
                "signal_take_profit": sig.get("take_profit_1"),
                "setup": sig.get("setup"),
                "decision": sig.get("decision"),
                "entry_confirmation": sig.get("entry_confirmation"),
                "price_action": sig.get("price_action"),
            })
        diagnostics["executed_directions"][direction] += 1

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

    # V12 trade quality metrics.
    winning_results = [
        trade["result"] for trade in trades
        if trade["result"] > 0
    ]

    losing_results = [
        trade["result"] for trade in trades
        if trade["result"] <= 0
    ]

    best_trade = max(
        (trade["result"] for trade in trades),
        default=0.0,
    )

    worst_trade = min(
        (trade["result"] for trade in trades),
        default=0.0,
    )

    long_win_rate = (
        sum(1 for trade in long_trades if trade["result"] > 0)
        / len(long_trades) * 100
        if long_trades else 0.0
    )

    short_win_rate = (
        sum(1 for trade in short_trades if trade["result"] > 0)
        / len(short_trades) * 100
        if short_trades else 0.0
    )

    average_winning_trade = (
        sum(winning_results) / len(winning_results)
        if winning_results else 0.0
    )

    average_losing_trade = (
        abs(sum(losing_results) / len(losing_results))
        if losing_results else 0.0
    )

    profit_loss_ratio = (
        average_winning_trade / average_losing_trade
        if average_losing_trade > 0
        else None
    )

    sorted_durations = sorted(trade_durations)

    median_trade_duration = (
        sorted_durations[len(sorted_durations) // 2]
        if sorted_durations and len(sorted_durations) % 2 == 1
        else (
            (
                sorted_durations[len(sorted_durations) // 2 - 1]
                + sorted_durations[len(sorted_durations) // 2]
            ) / 2
            if sorted_durations else 0.0
        )
    )

    # V13 monthly performance analytics.
    monthly_stats = {}

    for trade in trades:
        entry_index = trade["entry_index"]
        month_key = "UNKNOWN"

        if "timestamp" in work.columns:
            try:
                timestamp = pd.to_datetime(
                    work.iloc[entry_index]["timestamp"],
                    utc=True,
                    errors="coerce",
                )

                if not pd.isna(timestamp):
                    month_key = timestamp.strftime("%Y-%m")

            except (IndexError, KeyError, TypeError, ValueError):
                month_key = "UNKNOWN"

        if month_key not in monthly_stats:
            monthly_stats[month_key] = {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "net_profit": 0.0,
            }

        stats = monthly_stats[month_key]
        stats["trades"] += 1
        stats["net_profit"] += float(trade["result"])

        if trade["result"] > 0:
            stats["wins"] += 1
        else:
            stats["losses"] += 1

    for stats in monthly_stats.values():
        stats["win_rate"] = (
            stats["wins"] / stats["trades"] * 100
            if stats["trades"] else 0.0
        )
        stats["net_profit"] = float(stats["net_profit"])
        stats["win_rate"] = float(stats["win_rate"])

    diagnostics["near_miss_samples"] = sorted(
        diagnostics["near_miss_samples"],
        key=lambda sample: (
            -sample["passed_gate_count"],
            len(sample["failed_gates"]),
        ),
    )[:1000]

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
        "best_trade": float(best_trade),
        "worst_trade": float(worst_trade),
        "long_win_rate": float(long_win_rate),
        "short_win_rate": float(short_win_rate),
        "average_winning_trade": float(average_winning_trade),
        "average_losing_trade": float(average_losing_trade),
        "profit_loss_ratio": (
            float(profit_loss_ratio)
            if profit_loss_ratio is not None
            else None
        ),
        "median_trade_duration": float(median_trade_duration),
        "session_stats": session_stats,
        "monthly_stats": monthly_stats,
        "baseline": {
            "funnel": {
                "signal_evaluations": diagnostics["signal_evaluations"],
                "signal_exceptions": diagnostics["signal_exceptions"],
                "signal_statuses": diagnostics["signal_statuses"],
                "status_reasons": diagnostics["status_reasons"],
                "signal_directions": diagnostics["signal_directions"],
                "decision_states": diagnostics["decision_states"],
                "status_rejected": diagnostics["status_rejected"],
                "entry_not_ready": diagnostics["entry_not_ready"],
                "entry_ready": diagnostics["entry_ready"],
                "gate_failures": diagnostics["gate_failures"],
                "failed_gate_combinations": diagnostics["failed_gate_combinations"],
                "passed_gate_counts": diagnostics["passed_gate_counts"],
                "entry_confirmation_statuses": diagnostics[
                    "entry_confirmation_statuses"
                ],
                "entry_confirmation_reasons": diagnostics[
                    "entry_confirmation_reasons"
                ],
                "entry_check_statuses": diagnostics["entry_check_statuses"],
                "near_miss_samples": diagnostics["near_miss_samples"],
                "price_action_failures": diagnostics["price_action_failures"],
                "price_action_profile": diagnostics["price_action_profile"],
                "execution_rejections": diagnostics["execution_rejections"],
                "executed_trades": diagnostics["executed_trades"],
            },
            "performance": {
                "total_trades": len(trades),
                "winning_trades": len(wins),
                "losing_trades": len(losses),
                "win_rate": float(len(wins) / len(trades) * 100) if trades else 0.0,
                "net_profit": float(net_profit),
                "net_return": float((balance / capital - 1) * 100) if capital else 0.0,
                "average_r_multiple": float(average_r_multiple),
                "expectancy": float(expectancy),
                "profit_factor": float(gross_win / gross_loss) if gross_loss else None,
                "max_drawdown": float(max_dd * 100),
                "max_drawdown_amount": float(max_drawdown_amount),
            },
            "distribution": {
                "long_trades": len(long_trades),
                "short_trades": len(short_trades),
                "executed_directions": diagnostics["executed_directions"],
                "long_win_rate": float(long_win_rate),
                "short_win_rate": float(short_win_rate),
                "exit_reasons": exit_reason_breakdown,
            },
            "sessions": session_stats,
            "months": monthly_stats,
        },
        "diagnostics": diagnostics,
    }













