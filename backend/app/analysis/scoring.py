def score_setup(htf_bias, structure_bias, candle_direction, rr, min_rr, volume_ok, pattern_ok, sr_ok):
    factors={}
    factors["higher_timeframe_bias"]=20 if htf_bias==structure_bias and htf_bias!="NEUTRAL" else 0
    factors["market_structure"]=20 if structure_bias!="NEUTRAL" else 8
    factors["support_resistance"]=15 if sr_ok else 0
    factors["volume"]=10 if volume_ok else 0
    factors["momentum_pattern"]=10 if pattern_ok else 0
    factors["entry_confirmation"]=10 if candle_direction==structure_bias else 0
    factors["risk_reward"]=15 if rr>=min_rr else 0
    total=sum(factors.values())
    grade="A+" if total>=85 else "A" if total>=75 else "B" if total>=65 else "Weak" if total>=50 else "No trade"
    return total,grade,factors
