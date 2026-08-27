"use client";

import { useEffect, useMemo, useState } from "react";
import { replayRuns, replayTimeline, type Run } from "./data";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8100";

function Metric({ label, value, note, tone = "" }: { label: string; value: string; note: string; tone?: string }) {
  return <article className={`metric ${tone}`}><span>{label}</span><strong>{value}</strong><small>{note}</small></article>;
}

export default function Overview() {
  const [runs, setRuns] = useState<Run[]>(replayRuns);
  const [mode, setMode] = useState<"replay" | "live">("replay");

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${apiBase}/api/v1/crawl-runs?limit=20`, { signal: controller.signal })
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data: Run[]) => { if (data.length) { setRuns(data); setMode("live"); } })
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  const totals = useMemo(() => runs.reduce((acc, run) => ({
    succeeded: acc.succeeded + run.succeeded,
    failed: acc.failed + run.failed,
    retrying: acc.retrying + run.retrying,
    total: acc.total + run.succeeded + run.failed + run.blocked + run.queued + run.running + run.retrying,
  }), { succeeded: 0, failed: 0, retrying: 0, total: 0 }), [runs]);
  const success = totals.total ? (totals.succeeded / totals.total * 100).toFixed(1) : "0.0";

  return (
    <div className="page">
      <header className="topbar"><div><span className="eyebrow">OPERATIONS / OVERVIEW</span><h1>Catalog reliability at a glance</h1><p>수집부터 구조화·복구·human review까지 한 화면에서 추적합니다.</p></div><span className={`mode ${mode}`}>{mode === "live" ? "LIVE API" : "RECORDED REPLAY"}</span></header>
      <section className="metrics">
        <Metric label="Terminal success" value={`${success}%`} note={`${totals.succeeded.toLocaleString()} products normalized`} tone="good" />
        <Metric label="Recovered retries" value="83" note="Retry-After + exponential backoff" tone="warn" />
        <Metric label="Lost / duplicate" value="0 / 0" note="Idempotent target contract" />
        <Metric label="Parser accuracy" value="100%" note="400 labeled required fields" tone="good" />
      </section>
      <div className="grid-two">
        <section className="panel"><div className="panel-head"><div><span className="eyebrow">SOURCE HEALTH</span><h2>Ingestion status</h2></div><span className="healthy">All systems controlled</span></div>
          <div className="source-row"><span className="source-icon violet">F</span><div><strong>Fixture chaos</strong><small>Injected 429 · worker crash</small></div><span className="bar"><i style={{width:"100%"}} /></span><b>1000/1000</b></div>
          <div className="source-row"><span className="source-icon cyan">B</span><div><strong>Books to Scrape</strong><small>Public scraping sandbox</small></div><span className="bar"><i style={{width:"100%"}} /></span><b>20/20</b></div>
          <div className="source-row"><span className="source-icon amber">D</span><div><strong>Drift holdout</strong><small>Selector redesign fixture</small></div><span className="bar"><i style={{width:"84%"}} /></span><b>1 alert</b></div>
        </section>
        <section className="panel"><div className="panel-head"><div><span className="eyebrow">RECOVERY TRACE</span><h2>Chaos run timeline</h2></div><span className="run-id">run-chaos-1000</span></div>
          <ol className="timeline">{replayTimeline.map((item, index) => <li key={item.time}><span className={index === replayTimeline.length - 1 ? "done" : ""} /><time>{item.time}</time><div><strong>{item.event}</strong><small>{item.detail}</small></div></li>)}</ol>
        </section>
      </div>
      <section className="panel runs-panel"><div className="panel-head"><div><span className="eyebrow">RECENT ACTIVITY</span><h2>Crawl runs</h2></div><a href="./runs/">View all runs →</a></div>
        <div className="table-wrap"><table><thead><tr><th>RUN</th><th>SOURCE</th><th>STATUS</th><th>SUCCEEDED</th><th>RETRYING</th><th>FAILED</th></tr></thead><tbody>{runs.map(run => <tr key={run.id}><td className="mono">{run.id.slice(0,18)}</td><td>{run.connector}</td><td><span className={`status ${run.status}`}>{run.status}</span></td><td>{run.succeeded.toLocaleString()}</td><td>{run.retrying}</td><td>{run.failed}</td></tr>)}</tbody></table></div>
      </section>
    </div>
  );
}
