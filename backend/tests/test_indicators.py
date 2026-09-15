import pandas as pd
from app.analysis.indicators import add_indicators
def test_indicators():
    df=pd.DataFrame({"open":range(1,101),"high":range(2,102),"low":range(0,100),"close":range(1,101),"volume":[100]*100})
    out=add_indicators(df)
    assert "rsi" in out and "atr" in out and "ema_200" in out
    assert out["atr"].iloc[-1] > 0
