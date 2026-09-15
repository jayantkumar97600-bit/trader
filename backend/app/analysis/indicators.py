import numpy as np
import pandas as pd

def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def sma(s, n): return s.rolling(n).mean()

def rsi(close, n=14):
    d = close.diff()
    gain = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    loss = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def macd(close, fast=12, slow=26, signal=9):
    m = ema(close, fast) - ema(close, slow)
    s = ema(m, signal)
    return m, s, m - s

def atr(df, n=14):
    pc = df["close"].shift()
    tr = pd.concat([
        df["high"]-df["low"],
        (df["high"]-pc).abs(),
        (df["low"]-pc).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def vwap(df):
    pv = ((df["high"]+df["low"]+df["close"])/3) * df["volume"]
    return pv.cumsum() / df["volume"].replace(0, np.nan).cumsum()

def add_indicators(df, cfg=None):
    cfg = cfg or {}
    out = df.copy()
    for n in cfg.get("emas", [9,20,50,100,200]):
        out[f"ema_{n}"] = ema(out["close"], n)
    for n in cfg.get("smas", [20,50,200]):
        out[f"sma_{n}"] = sma(out["close"], n)
    out["rsi"] = rsi(out["close"], cfg.get("rsi_period",14))
    out["macd"], out["macd_signal"], out["macd_hist"] = macd(out["close"])
    out["atr"] = atr(out, cfg.get("atr_period",14))
    out["vwap"] = vwap(out)
    mid = out["close"].rolling(20).mean()
    std = out["close"].rolling(20).std()
    out["bb_mid"] = mid
    out["bb_upper"] = mid + 2*std
    out["bb_lower"] = mid - 2*std
    out["volume_ma"] = out["volume"].rolling(20).mean()
    return out
