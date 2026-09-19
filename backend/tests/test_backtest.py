import pandas as pd

from app.analysis.backtest import backtest


def make_data(rows=160, target_indices=None):
    target_indices = set(target_indices or [])

    return pd.DataFrame({
        "open": [100.0] * rows,
        "high": [
            101.5 if i in target_indices else 100.5
            for i in range(rows)
        ],
        "low": [99.5] * rows,
        "close": [100.0] * rows,
    })


def ready_signal(part):
    return {
        "status": "READY",
        "direction": "LONG",
        "entry": 100.0,
        "stop_loss": 99.0,
        "take_profit_1": 101.0,
        "decision": {"entry_ready": True},
    }


def test_backtest_returns_summary():
    df = make_data(target_indices=[130, 150])

    result = backtest(
        df,
        ready_signal,
        capital=10000,
        risk_pct=1,
        max_bars=100,
        step=10,
    )

    assert isinstance(result, dict)
    assert "total_trades" in result
    assert "final_balance" in result
    assert "max_drawdown" in result


def test_backtest_does_not_open_overlapping_positions():
    df = make_data(target_indices=[130, 150])

    result = backtest(
        df,
        ready_signal,
        capital=10000,
        risk_pct=1,
        max_bars=100,
        step=1,
    )

    trades = result["trades"]

    for previous, current in zip(trades, trades[1:]):
        assert current["entry_index"] > previous["exit_index"]


def test_backtest_handles_no_trade_signal():
    df = make_data()

    def no_trade_signal(part):
        return {
            "status": "WAIT",
            "direction": "LONG",
            "decision": {"entry_ready": False},
        }

    result = backtest(
        df,
        no_trade_signal,
        capital=10000,
        max_bars=100,
        step=10,
    )

    assert result["total_trades"] == 0




def test_backtest_handles_gap_at_entry():
    df = make_data(rows=160, target_indices=[70])

    def gap_signal(part):
        return {
            "status": "READY",
            "direction": "LONG",
            "entry": 100.0,
            "stop_loss": 99.0,
            "take_profit_1": 101.0,
            "decision": {"entry_ready": True},
        }

    df.loc[121, "open"] = 100.8
    df.loc[121, "high"] = 101.2
    df.loc[121, "low"] = 100.7

    result = backtest(
        df,
        gap_signal,
        capital=10000,
        risk_pct=1,
        max_bars=100,
        step=1,
    )

    assert isinstance(result, dict)
    assert "trades" in result
    assert result["total_trades"] >= 1
    assert result["trades"][0]["entry"] == 100.8

def test_long_gap_beyond_stop_is_rejected():
    df = make_data(rows=160)

    def gap_signal(part):
        return {
            "status": "READY",
            "direction": "LONG",
            "entry": 100.0,
            "stop_loss": 99.0,
            "take_profit_1": 101.0,
            "decision": {"entry_ready": True},
        }

    df.loc[121, "open"] = 98.0

    result = backtest(
        df, gap_signal, capital=10000,
        risk_pct=1, max_bars=100, step=1
    )

    assert result["total_trades"] == 0


def test_long_gap_beyond_target_closes_immediately():
    df = make_data(rows=160)

    def gap_signal(part):
        return {
            "status": "READY",
            "direction": "LONG",
            "entry": 100.0,
            "stop_loss": 99.0,
            "take_profit_1": 101.0,
            "decision": {"entry_ready": True},
        }

    df.loc[121, "open"] = 102.0

    result = backtest(
        df, gap_signal, capital=10000,
        risk_pct=1, max_bars=100, step=1
    )

    assert result["total_trades"] >= 1
    assert result["trades"][0]["entry"] == 102.0
    assert result["trades"][0]["exit_reason"] == "TAKE_PROFIT_GAP"


def test_short_gap_beyond_stop_is_rejected():
    df = make_data(rows=160)

    def gap_signal(part):
        return {
            "status": "READY",
            "direction": "SHORT",
            "entry": 100.0,
            "stop_loss": 101.0,
            "take_profit_1": 99.0,
            "decision": {"entry_ready": True},
        }

    df.loc[121, "open"] = 102.0

    result = backtest(
        df, gap_signal, capital=10000,
        risk_pct=1, max_bars=100, step=1
    )

    assert result["total_trades"] == 0


def test_backtest_applies_commission():
    df = make_data(rows=160, target_indices=[130])

    result = backtest(
        df,
        ready_signal,
        capital=10000,
        risk_pct=1,
        commission_bps=10,
        slippage=0,
        max_bars=100,
        step=1,
    )

    assert result["total_trades"] >= 1
    assert result["trades"][0]["fees"] > 0
    assert result["trades"][0]["result"] < result["trades"][0]["gross_result"]


def test_backtest_applies_slippage():
    df = make_data(rows=160, target_indices=[130])

    result = backtest(
        df,
        ready_signal,
        capital=10000,
        risk_pct=1,
        commission_bps=0,
        slippage=0.1,
        max_bars=100,
        step=1,
    )

    assert result["total_trades"] >= 1
    assert result["trades"][0]["slippage_cost"] > 0
    assert result["trades"][0]["result"] < result["trades"][0]["gross_result"]


def test_short_take_profit_generates_positive_profit():
    df = make_data(rows=160)

    def short_signal(part):
        return {
            "status": "READY",
            "direction": "SHORT",
            "entry": 100.0,
            "stop_loss": 101.0,
            "take_profit_1": 99.0,
            "decision": {"entry_ready": True},
        }

    df.loc[121, "open"] = 100.0
    df.loc[121, "low"] = 98.5

    result = backtest(
        df,
        short_signal,
        capital=10000,
        risk_pct=1,
        commission_bps=0,
        slippage=0,
        max_bars=100,
        step=1,
    )

    assert result["total_trades"] >= 1
    assert result["trades"][0]["gross_result"] > 0
    assert result["trades"][0]["exit_reason"] == "TAKE_PROFIT"


def test_backtest_profit_factor_is_calculated_correctly():
    df = make_data(rows=160, target_indices=[130, 150])

    result = backtest(
        df,
        ready_signal,
        capital=10000,
        risk_pct=1,
        commission_bps=0,
        slippage=0,
        max_bars=100,
        step=1,
    )

    trades = result["trades"]

    gross_win = sum(
        trade["result"] for trade in trades
        if trade["result"] > 0
    )

    gross_loss = abs(sum(
        trade["result"] for trade in trades
        if trade["result"] <= 0
    ))

    expected_factor = (
        gross_win / gross_loss
        if gross_loss > 0
        else None
    )

    assert result["profit_factor"] == expected_factor


def test_backtest_drawdown_is_valid_percentage():
    df = make_data(rows=160, target_indices=[130, 150])

    result = backtest(
        df,
        ready_signal,
        capital=10000,
        risk_pct=1,
        commission_bps=0,
        slippage=0,
        max_bars=100,
        step=1,
    )

    assert result["max_drawdown"] >= 0
    assert result["max_drawdown"] <= 100


def test_backtest_net_return_matches_final_balance():
    capital = 10000

    df = make_data(rows=160, target_indices=[130, 150])

    result = backtest(
        df,
        ready_signal,
        capital=capital,
        risk_pct=1,
        commission_bps=0,
        slippage=0,
        max_bars=100,
        step=1,
    )

    expected_return = (
        (result["final_balance"] / capital) - 1
    ) * 100

    assert abs(
        result["net_return"] - expected_return
    ) < 1e-9


def test_backtest_trade_accounting_is_consistent():
    df = make_data(rows=160, target_indices=[130, 150])

    result = backtest(
        df,
        ready_signal,
        capital=10000,
        risk_pct=1,
        commission_bps=0,
        slippage=0,
        max_bars=100,
        step=1,
    )

    assert (
        result["winning_trades"] +
        result["losing_trades"]
    ) == result["total_trades"]

    assert result["final_balance"] > 0


def test_backtest_v8_risk_metrics_exist():
    df = make_data(rows=160, target_indices=[130, 150])

    result = backtest(
        df,
        ready_signal,
        capital=10000,
        risk_pct=1,
        commission_bps=0,
        slippage=0,
        max_bars=100,
        step=1,
    )

    assert "equity_curve" in result
    assert "average_win" in result
    assert "average_loss" in result
    assert "max_consecutive_wins" in result
    assert "max_consecutive_losses" in result

    assert isinstance(result["equity_curve"], list)
    assert len(result["equity_curve"]) >= 1
    assert result["max_consecutive_wins"] >= 0
    assert result["max_consecutive_losses"] >= 0


def test_backtest_equity_curve_ends_at_final_balance():
    df = make_data(rows=160, target_indices=[130, 150])

    result = backtest(
        df,
        ready_signal,
        capital=10000,
        risk_pct=1,
        commission_bps=0,
        slippage=0,
        max_bars=100,
        step=1,
    )

    assert result["equity_curve"][-1] == result["final_balance"]


def test_backtest_average_metrics_are_numeric():
    df = make_data(rows=160, target_indices=[130, 150])

    result = backtest(
        df,
        ready_signal,
        capital=10000,
        risk_pct=1,
        commission_bps=0,
        slippage=0,
        max_bars=100,
        step=1,
    )

    assert isinstance(result["average_win"], float)
    assert isinstance(result["average_loss"], float)

