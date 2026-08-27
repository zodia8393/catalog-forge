"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  displayConnector,
  displayStatus,
  recordedAt,
  recordedMetrics,
  recordedSources,
  replayRuns,
  replayTimeline,
  type Run,
} from "./data";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;

function Metric({ label, value, note, tone = "" }: { label: string; value: string; note: string; tone?: string }) {
  return (
    <article className={"metric " + tone}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}

export default function Overview() {
  const [runs, setRuns] = useState<Run[]>(replayRuns);
  const [mode, setMode] = useState<"replay" | "live">("replay");

  useEffect(() => {
    if (!apiBase) return;
    const controller = new AbortController();
    fetch(apiBase + "/api/v1/crawl-runs?limit=20", { signal: controller.signal })
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
  const success = mode === "replay"
    ? (recordedMetrics.success_rate * 100).toFixed(1)
    : totals.total ? (totals.succeeded / totals.total * 100).toFixed(1) : "0.0";
  const completed = mode === "replay" ? recordedMetrics.succeeded : totals.succeeded;
  const sourceIconClasses = ["violet", "cyan", "amber"];

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <span className="eyebrow">운영 현황 / 한눈에 보기</span>
          <h1>상품 데이터 수집 상태를 한눈에</h1>
          <p>수집부터 구조화, 장애 복구, 사람 검수까지 한 화면에서 추적합니다.</p>
        </div>
        <div className="top-actions">
          <span className={"mode " + (mode === "live" ? "live" : "recorded")}>{mode === "live" ? "실시간 API" : "실제 실행 기록"}</span>
          <Link className="action-link primary-action" href="/playground/">직접 입력해보기 <span>→</span></Link>
        </div>
      </header>
      <section className="demo-note" aria-label="데모 안내">
        <strong>실제 실행으로 만든 읽기 전용 snapshot입니다.</strong>
        <span>{recordedAt} KST에 외부 sandbox 수집과 로컬 장애 주입 pipeline을 실행해 기록했습니다.</span>
        <Link href="/playground/">내 HTML로 실시간 체험 →</Link>
      </section>
      <section className="metrics">
        <Metric label="최종 수집 성공률" value={success + "%"} note={"대상 " + completed.toLocaleString() + "건 실제 처리"} tone="good" />
        <Metric label="복구한 일시 오류" value={recordedMetrics.transient_failures_recovered + " / " + recordedMetrics.transient_failures} note="실제 429 attempt를 재시도" tone="warn" />
        <Metric label="데이터 유실 / 중복" value={recordedMetrics.lost_snapshots + " / " + recordedMetrics.duplicate_snapshots} note="target_id 기준 snapshot 재계산" />
        <Metric label="표본 필수 필드" value={recordedMetrics.required_fields_present + " / " + recordedMetrics.required_fields_expected} note="제목·가격·통화·재고 실제 결과" tone="good" />
      </section>
      <div className="grid-two">
        <section className="panel">
          <div className="panel-head">
            <div><span className="eyebrow">수집처 상태</span><h2>수집·복구 검증 결과</h2></div>
            <span className="healthy">모든 검증 완료</span>
          </div>
          {recordedSources.map((source, index) => (
            <div className="source-row" key={source.source}>
              <span className={"source-icon " + sourceIconClasses[index]}>{source.label.slice(0, 1)}</span>
              <div><strong>{source.label}</strong><small>{source.description}</small></div>
              <span className="bar"><i style={{width: (source.succeeded / source.targets * 100) + "%"}} /></span>
              <b>{source.reviews_pending ? "검수 " + source.reviews_pending + "건" : source.succeeded + "/" + source.targets}</b>
            </div>
          ))}
        </section>
        <section className="panel"><div className="panel-head"><div><span className="eyebrow">실행 기록</span><h2>실제로 처리된 순서</h2></div><span className="run-id" title={replayRuns[0].id}>{replayRuns[0].id.slice(0, 13)}…</span></div>
          <ol className="timeline">{replayTimeline.map((item, index) => <li key={item.time}><span className={index === replayTimeline.length - 1 ? "done" : ""} /><time>{item.time}</time><div><strong>{item.event}</strong><small>{item.detail}</small></div></li>)}</ol>
        </section>
      </div>
      <section className="panel runs-panel"><div className="panel-head"><div><span className="eyebrow">최근 활동</span><h2>수집 실행 기록</h2></div><Link href="/runs/">전체 실행 보기 →</Link></div>
        <div className="table-wrap"><table><thead><tr><th>실행 ID</th><th>수집처</th><th>상태</th><th>성공</th><th>재시도 중</th><th>실패</th></tr></thead><tbody>{runs.map(run => <tr key={run.id}><td className="mono">{run.id.slice(0,18)}</td><td>{displayConnector(run.connector)}</td><td><span className={"status " + run.status}>{displayStatus(run.status)}</span></td><td>{run.succeeded.toLocaleString()}</td><td>{run.retrying}</td><td>{run.failed}</td></tr>)}</tbody></table></div>
      </section>
    </div>
  );
}
