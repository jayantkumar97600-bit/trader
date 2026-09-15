from app.analysis.risk import risk_plan
def test_position_size():
    x=risk_plan(20000,1,500,490,520)
    assert round(x["risk_amount"],2)==200
    assert round(x["quantity"],2)==20
    assert round(x["rr"],2)==2
