import MetaTrader5 as mt5

if not mt5.initialize():
    print("MT5 connection failed")
    print(mt5.last_error())
    raise SystemExit

print("MT5 CONNECTED")

info = mt5.symbol_info("XAUUSD")

if info is None:
    print("XAUUSD not found")
else:
    print("Symbol:", info.name)
    print("Bid:", info.bid)
    print("Ask:", info.ask)

mt5.shutdown()