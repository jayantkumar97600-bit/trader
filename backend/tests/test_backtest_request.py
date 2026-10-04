import pytest
from pydantic import ValidationError

from app.api.routes import BacktestRequest


def test_backtest_request_uses_validation_defaults():
    request = BacktestRequest()

    assert request.backtest_bars == 5000
    assert request.backtest_step == 15


def test_backtest_request_rejects_invalid_window_settings():
    with pytest.raises(ValidationError):
        BacktestRequest(backtest_bars=99)

    with pytest.raises(ValidationError):
        BacktestRequest(backtest_step=0)
