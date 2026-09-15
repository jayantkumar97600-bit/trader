def candlesticks(df):
    out=[]
    if len(df)<3: return out
    for i in range(max(1,len(df)-50),len(df)):
        r=df.iloc[i]; prev=df.iloc[i-1]
        body=abs(r.close-r.open); rng=max(r.high-r.low,1e-12)
        upper=r.high-max(r.open,r.close); lower=min(r.open,r.close)-r.low
        if body/rng < .1: out.append({"index":i,"name":"Doji","direction":"NEUTRAL"})
        if lower > body*2 and upper < body: out.append({"index":i,"name":"Hammer","direction":"BULLISH"})
        if upper > body*2 and lower < body: out.append({"index":i,"name":"Shooting star","direction":"BEARISH"})
        if r.close>r.open and prev.close<prev.open and r.close>=prev.open and r.open<=prev.close:
            out.append({"index":i,"name":"Bullish engulfing","direction":"BULLISH"})
        if r.close<r.open and prev.close>prev.open and r.open>=prev.close and r.close<=prev.open:
            out.append({"index":i,"name":"Bearish engulfing","direction":"BEARISH"})
        if rng>0 and body/rng>.7: out.append({"index":i,"name":"Strong momentum candle","direction":"BULLISH" if r.close>r.open else "BEARISH"})
    return out

def chart_patterns(df):
    out=[]
    if len(df)<30: return out
    recent=df.tail(30)
    hi=recent.high; lo=recent.low
    # Conservative range/triangle heuristics, explicitly labeled as heuristic detections.
    if (hi.max()-hi.min())/recent.close.mean()<.012 and (lo.max()-lo.min())/recent.close.mean()<.012:
        out.append({"name":"Rectangle","direction":"NEUTRAL","confirmation":"UNCONFIRMED","quality":55})
    if hi.iloc[:15].max() < hi.iloc[15:].max() and lo.iloc[:15].min() < lo.iloc[15:].min():
        out.append({"name":"Ascending structure","direction":"BULLISH","confirmation":"UNCONFIRMED","quality":52})
    return out
