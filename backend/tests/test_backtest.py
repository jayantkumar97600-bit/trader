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


