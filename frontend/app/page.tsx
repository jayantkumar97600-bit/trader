"use client";
import { useEffect, useState } from "react";
import Chart from "../components/Chart";
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TFS = ["1m","3m","5m","15m","30m","1h","4h","1d","1w"];

export default function Home() {
  const [asset, setAsset] = useState("XAUUSD");
  const [timeframe, setTimeframe] = useState("15m");
  const [data, setData] = useState<any>(null);
  const [candles, setCandles] = useState<any[]>([]);
  const [bt, setBt] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [chartLoading, setChartLoading] = useState(false);

  async function loadChart() {
    setChartLoading(true);
    try {
      const r = await fetch(`${API}/api/candles?asset=${asset}&timeframe=${timeframe}&limit=500`);
      const j = await r.json(); setCandles(j.candles || []);
    } finally { setChartLoading(false); }
  }
  async function analyze() {
    setLoading(true); setBt(null);
    try {
      const r = await fetch(`${API}/api/analyze`, { method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({asset, timeframe, htf_timeframe:"1h", capital:10000, risk_pct:1, min_rr:2}) });
      setData(await r.json());
      await loadChart();
    } finally { setLoading(false); }
  }
  async function backtest() {
    const r = await fetch(`${API}/api/backtest`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({asset,timeframe,capital:10000,risk_pct:1,min_rr:2})});
    setBt(await r.json());
  }
  useEffect(() => { analyze(); }, [timeframe]);

  return <main>
    <header><div><div className="eyebrow">RESEARCH TERMINAL</div><h1>AI Trading Analyzer</h1></div>
      <div className="controls"><select value={asset} onChange={e=>setAsset(e.target.value)}><option>XAUUSD</option><option>BTCUSD</option><option>NIFTY</option><option>EURUSD</option></select>
      <select value={timeframe} onChange={e=>setTimeframe(e.target.value)}>{TFS.map(x=><option key={x}>{x}</option>)}</select></div>
    </header>
    <div className="notice">Data source · <b>MT5 historical CSV</b> · Live market data is not connected yet.</div>
    {loading ? <div className="card">Loading real MT5 data…</div> : data && <>
      <section className="grid">
        <div className="card hero"><span>STATUS</span><strong>{data.status}</strong><small>{data.direction||"—"} · {data.grade||""}</small></div>
        <div className="card"><span>SETUP SCORE</span><strong>{data.score??"—"}/100</strong><small>{data.grade||"—"}</small></div>
        <div className="card"><span>R:R</span><strong>{data.rr?`1:${data.rr.toFixed(2)}`:"—"}</strong><small>Minimum 1:2</small></div>
        <div className="card"><span>POSITION SIZE</span><strong>{data.quantity?data.quantity.toFixed(2):"—"}</strong><small>Risk ₹{data.risk_amount?.toFixed(2)||"—"}</small></div>
      </section>
      <section className="two"><div className="panel"><div className="row"><h2>XAUUSD · {timeframe}</h2><small>{chartLoading?"Loading…":`${candles.length} candles`}</small></div><Chart candles={candles}/></div>
        <div className="panel"><h2>Trade plan</h2><div className="levels"><div>Entry <b>{data.entry?.toFixed(4)||"—"}</b></div><div>SL <b>{data.stop_loss?.toFixed(4)||"—"}</b></div><div>TP1 <b>{data.take_profit_1?.toFixed(4)||"—"}</b></div></div>
        <h3>Why</h3><ul>{(data.reasons||[]).map((x:string,i:number)=><li key={i}>{x}</li>)}</ul><h3>Invalidation</h3><p>{data.invalidation||"—"}</p></div></section>
        <section className="panel"><h2>Analysis details</h2><div className="tags">{(data.candlesticks||[]).map((x:any,i:number)=><span key={i}>{x.name}</span>)}{(data.chart_patterns||[]).map((x:any,i:number)=><span key={i}>{x.name}</span>)}</div><pre>{JSON.stringify(data.score_factors,null,2)}</pre></section>
      </>}
    <section className="panel"><div className="row"><h2>Backtest</h2><button onClick={backtest}>Run</button></div>{bt&&<div className="stats">{Object.entries(bt).filter(([k])=>k!=="trades").map(([k,v]:any)=><div key={k}><span>{k}</span><b>{typeof v==="number"?v.toFixed(2):String(v)}</b></div>)}</div>}</section>
    <footer>Decision support only. Setup score is not a win probability. No guaranteed outcomes.</footer>
  </main>
}
