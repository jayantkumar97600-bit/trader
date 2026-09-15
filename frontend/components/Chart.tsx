"use client";
import { useEffect, useRef } from "react";
import { createChart, ColorType } from "lightweight-charts";

export default function Chart({ candles }: { candles: any[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      height: 460,
      layout: { textColor: "#d7dbe5", background: { type: ColorType.Solid, color: "#0d1117" } },
      grid: { vertLines: { color: "#202733" }, horzLines: { color: "#202733" } },
      rightPriceScale: { borderColor: "#303846" }, timeScale: { borderColor: "#303846" },
    });
    const series = chart.addCandlestickSeries({
      upColor: "#26a69a", downColor: "#ef5350", borderVisible: false,
      wickUpColor: "#26a69a", wickDownColor: "#ef5350",
    });
    series.setData(candles || []);
    chart.timeScale().fitContent();
    const resize = () => chart.applyOptions({ width: ref.current?.clientWidth || 800 });
    window.addEventListener("resize", resize); resize();
    return () => { window.removeEventListener("resize", resize); chart.remove(); };
  }, [candles]);
  return <div ref={ref} style={{ width: "100%" }} />;
}
