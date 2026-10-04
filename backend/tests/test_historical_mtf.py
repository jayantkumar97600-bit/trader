import pandas as pd

from app.api.routes import AnalyzeRequest, _load_mtf, _timeframe_duration


def _frame(timestamps):
    return pd.DataFrame({
        "timestamp": pd.to_datetime(timestamps, utc=True),
        "open": [1.0] * len(timestamps),
        "high": [1.0] * len(timestamps),
        "low": [1.0] * len(timestamps),
        "close": [1.0] * len(timestamps),
        "volume": [1.0] * len(timestamps),
    })


def test_historical_mtf_cutoff_excludes_future_candles():
    req = AnalyzeRequest()
    source_frames = {
        tf: _frame(pd.date_range(
            "2025-01-01T00:00:00Z",
            "2025-01-01T12:00:00Z",
            freq=_timeframe_duration(tf),
        ))
        for tf in ("4h", "1h", "15m", "5m")
    }

    cutoff = pd.Timestamp("2025-01-01T12:00:00Z")
    frames = _load_mtf(req, cutoff=cutoff, source_frames=source_frames)

    for tf, frame_df in frames.items():
        candle_closes = frame_df["timestamp"] + _timeframe_duration(tf)
        assert candle_closes.max() == cutoff
        assert (candle_closes <= cutoff).all()


def test_historical_mtf_cutoff_advances_with_source_candle():
    req = AnalyzeRequest()
    source_frames = {
        tf: _frame(pd.date_range(
            "2025-01-01T00:00:00Z",
            "2025-01-01T16:00:00Z",
            freq=_timeframe_duration(tf),
        ))
        for tf in ("4h", "1h", "15m", "5m")
    }

    first = _load_mtf(
        req,
        cutoff=pd.Timestamp("2025-01-01T12:00:00Z"),
        source_frames=source_frames,
    )
    second = _load_mtf(
        req,
        cutoff=pd.Timestamp("2025-01-01T16:00:00Z"),
        source_frames=source_frames,
    )

    for tf in first:
        assert len(first[tf]) < len(second[tf])
        assert first[tf]["timestamp"].iloc[-1] < second[tf]["timestamp"].iloc[-1]
