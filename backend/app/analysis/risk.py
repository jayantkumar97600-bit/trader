def risk_plan(capital, risk_pct, entry, stop, target1, contract_size=1.0, tick_size=None, tick_value=None):
    risk_amount=capital*risk_pct/100
    per_unit=abs(entry-stop)
    if per_unit<=0: raise ValueError("Entry and stop must differ.")
    qty=risk_amount/per_unit
    reward=abs(target1-entry)
    rr=reward/per_unit
    return {"risk_amount":risk_amount,"quantity":qty,"entry":entry,"stop_loss":stop,
            "take_profit_1":target1,"rr":rr,"contract_size":contract_size,
            "tick_size":tick_size,"tick_value":tick_value}

def levels_from_atr(direction, entry, atr_value, sl_atr=1.5, tp_atr=3.0):
    if direction=="LONG":
        return entry-atr_value*sl_atr, entry+atr_value*tp_atr
    return entry+atr_value*sl_atr, entry-atr_value*tp_atr
