# AI Trading Analysis Terminal — MVP

A transparent, testable trading decision-support system based on the supplied specification. It is **analysis-only by default** and does not place broker orders.

## MVP capabilities
- Historical OHLCV CSV loading
- Technical indicators: EMA 9/20/50/100/200, SMA, RSI, MACD, ATR, VWAP, Bollinger Bands, volume MA
- Market structure: swing highs/lows, BOS, CHoCH, internal/external labels
- Basic candlestick patterns
- Basic chart-pattern detection
- Multi-timeframe bias/structure/confirmation
- Transparent 0–100 setup score
- Entry/SL/TP and R:R calculation
- Instrument-aware position sizing configuration
- Backtesting with commission, spread and slippage
- SQLite trade journal for the local MVP
- FastAPI backend + Next.js frontend
- Automated tests
- Explicit `NO TRADE`, `Insufficient data`, and live-data-unavailable states

## Important
This MVP does not claim a score is a probability of winning. No live prices are invented. If no live adapter is configured, the UI says `Live market data unavailable.`

## Run

### Backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

### Demo data
A deterministic sample CSV is included at `data/demo_xauusd.csv`. It is **synthetic demonstration data**, not live or historical market data. Replace it with a real OHLCV CSV before using the analyzer for research.

Expected CSV columns:
`timestamp,open,high,low,close,volume`

## API
- `GET /api/health`
- `POST /api/analyze`
- `POST /api/backtest`
- `POST /api/journal`
- `GET /api/journal`
- `GET /api/config`

## Architecture
`DATA → CALCULATION → SIGNAL → AI EXPLANATION`

The AI explanation service is intentionally isolated. The deterministic analysis layer owns all numerical values so an LLM cannot invent prices or indicator values.
