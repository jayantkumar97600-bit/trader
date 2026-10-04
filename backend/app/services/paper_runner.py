from datetime import datetime, timezone
from typing import Any, Callable

from app.api.routes import AnalyzeRequest, getdf, make_signal
from app.services.data_freshness import get_latest_completed_candle_age_seconds
from app.services.journal import get_open_trades
from app.services.mt5_incremental import refresh_incremental
from app.services.mt5_price import get_current_price
from app.services.paper_monitor import monitor_open_trades
from app.services.paper_trading import create_paper_trade


def run_single_cycle(
    analysis: dict[str, Any] | None = None,
    symbol: str = "XAUUSD",
    capital: float = 10000.0,
    risk_pct: float = 0.5,
    max_tick_age_seconds: int = 300,
    price_provider: Callable[..., dict[str, Any]] | None = None,
    refresh_provider: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Execute exactly one safe paper-trading cycle.

    No real MT5 orders are ever submitted.
    """

    cycle_time = datetime.now(timezone.utc).isoformat()

    if price_provider is None:
        price_provider = get_current_price

    if refresh_provider is None:
        refresh_provider = refresh_incremental

    # ---------------------------------------------------------
    # 1. FRESH PRICE GUARD
    # ---------------------------------------------------------

    price = price_provider(
        symbol=symbol,
        max_age_seconds=max_tick_age_seconds,
    )

    if not price["fresh"]:
        return {
            "status": "STALE_PRICE",
            "action": "NO_ACTION",
            "cycle_timestamp": cycle_time,
            "price": price,
            "refresh": None,
            "data_freshness": None,
            "analysis": None,
            "opened": None,
            "closed": [],
        }

    # ---------------------------------------------------------
    # 2. INCREMENTAL DATA REFRESH
    # ---------------------------------------------------------

    try:
        refresh_result = refresh_provider()
    except Exception as exc:
        return {
            "status": "REFRESH_ERROR",
            "action": "NO_ACTION",
            "cycle_timestamp": cycle_time,
            "price": price,
            "refresh": {
                "status": "ERROR",
                "error": str(exc),
            },
            "data_freshness": None,
            "analysis": None,
            "opened": None,
            "closed": [],
        }

    refresh_status = refresh_result.get("status")

    if refresh_status not in {"UPDATED", "NO_NEW_DATA"}:
        return {
            "status": "REFRESH_REJECTED",
            "action": "NO_ACTION",
            "cycle_timestamp": cycle_time,
            "price": price,
            "refresh": refresh_result,
            "data_freshness": None,
            "analysis": None,
            "opened": None,
            "closed": [],
        }

    # ---------------------------------------------------------
    # 3. DATA FRESHNESS GUARD
    # ---------------------------------------------------------

    data_freshness = get_latest_completed_candle_age_seconds(
        current_timestamp=price["timestamp"],
    )

    if data_freshness["status"] != "OK":
        return {
            "status": "STALE_MARKET_DATA",
            "action": "NO_ACTION",
            "cycle_timestamp": cycle_time,
            "price": price,
            "refresh": refresh_result,
            "data_freshness": data_freshness,
            "analysis": None,
            "opened": None,
            "closed": [],
        }

    # ---------------------------------------------------------
    # 4. MONITOR EXISTING PAPER TRADES
    # ---------------------------------------------------------

    monitor_result = monitor_open_trades(
        symbol=symbol,
        max_tick_age_seconds=max_tick_age_seconds,
        price=price,
    )

    open_trades = get_open_trades()

    if open_trades:
        return {
            "status": "OPEN_TRADE_EXISTS",
            "action": "MONITOR_ONLY",
            "cycle_timestamp": cycle_time,
            "price": price,
            "refresh": refresh_result,
            "data_freshness": data_freshness,
            "analysis": None,
            "opened": None,
            "closed": monitor_result.get("closed", []),
            "open_trade_ids": [
                trade["id"] for trade in open_trades
            ],
        }

    # ---------------------------------------------------------
    # 5. ANALYSIS
    # ---------------------------------------------------------

    if analysis is None:
        request = AnalyzeRequest(
            asset=symbol,
            csv_path="mt5/XAUUSD_M15.csv",
            capital=capital,
            risk_pct=risk_pct,
            min_rr=2.0,
            timeframe="15m",
            htf_timeframe="1h",
            hierarchy=["4h", "1h", "15m", "5m"],
        )

        df = getdf(
            request.csv_path,
            request.timeframe,
            request.asset,
            5000,
        )

        analysis = make_signal(df, request)

    # ---------------------------------------------------------
    # 6. FROZEN PAPER STRATEGY
    # ---------------------------------------------------------

    created = create_paper_trade(
        analysis=analysis,
        capital=capital,
        risk_pct=risk_pct,
    )

    return {
        "status": "SIGNAL_EVALUATED",
        "action": (
            "PAPER_TRADE_CREATED"
            if created.get("created")
            else "NO_SIGNAL"
        ),
        "cycle_timestamp": cycle_time,
        "price": price,
        "refresh": refresh_result,
        "data_freshness": data_freshness,
        "analysis": {
            "status": analysis.get("status"),
            "timestamp": analysis.get("timestamp"),
            "direction": analysis.get("direction"),
            "entry": analysis.get("entry"),
            "stop_loss": analysis.get("stop_loss"),
            "take_profit_1": analysis.get("take_profit_1"),
            "rr": analysis.get("rr"),
        },
        "opened": created if created.get("created") else None,
        "closed": monitor_result.get("closed", []),
    }
