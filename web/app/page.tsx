"use client";

import { useEffect, useMemo, useState } from "react";
import {
  displayConnector,
  displayStatus,
  replayRuns,
  replayTimeline,
  type Run,
} from "./data";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8100";

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
  const success = totals.total ? (totals.succeeded / totals.total * 100).toFixed(1) : "0.0";

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <span className="eyebrow">운영 현황 / 한눈에 보기</span>
          <h1>상품 데이터 수집 상태를 한눈에</h1>
          <p>수집부터 구조화, 장애 복구, 사람 검수까지 한 화면에서 추적합니다.</p>
        </div>
        <span className={"mode " + mode}>{mode === "live" ? "실시간 API" : "검증 결과 재생"}</span>
      </header>
      <section className="demo-note" aria-label="데모 안내">
        <strong>이 화면은 읽기 전용 데모입니다.</strong>
        <span>1,000건 장애 복구 훈련과 공개 샌드박스 수집 결과를 저장해 재생합니다.</span>
      </section>
      <section className="metrics">
        <Metric label="최종 수집 성공률" value={success + "%"} note={"대상 " + totals.succeeded.toLocaleString() + "건 처리 완료"} tone="good" />
        <Metric label="복구한 일시 오류" value="83 / 83" note="Retry-After와 지수 백오프로 재시도" tone="warn" />
        <Metric label="데이터 유실 / 중복" value="0 / 0" note="target_id 기준 중복 저장 방지" />
        <Metric label="필수 필드 정확도" value="400 / 400" note="제목·가격·통화·재고 라벨 검증" tone="good" />
      </section>
      <div className="grid-two">
        <section className="panel">
          <div className="panel-head">
            <div><span className="eyebrow">수집처 상태</span><h2>수집·복구 검증 결과</h2></div>
            <span className="healthy">모든 검증 완료</span>
          </div>
          <div className="source-row"><span className="source-icon violet">F</span><div><strong>장애 복구 테스트</strong><small>429 오류와 작업자 중단 주입</small></div><span className="bar"><i style={{width:"100%"}} /></span><b>1000/1000</b></div>
          <div className="source-row"><span className="source-icon cyan">B</span><div><strong>Books to Scrape</strong><small>공개 스크래핑 연습 사이트</small></div><span className="bar"><i style={{width:"100%"}} /></span><b>20/20</b></div>
          <div className="source-row"><span className="source-icon amber">D</span><div><strong>구조 변경 테스트</strong><small>HTML 구조 변경 감지</small></div><span className="bar"><i style={{width:"84%"}} /></span><b>검수 1건</b></div>
        </section>
        <section className="panel"><div className="panel-head"><div><span className="eyebrow">복구 기록</span><h2>장애가 복구된 순서</h2></div><span className="run-id">run-chaos-1000</span></div>
          <ol className="timeline">{replayTimeline.map((item, index) => <li key={item.time}><span className={index === replayTimeline.length - 1 ? "done" : ""} /><time>{item.time}</time><div><strong>{item.event}</strong><small>{item.detail}</small></div></li>)}</ol>
        </section>
      </div>
      <section className="panel runs-panel"><div className="panel-head"><div><span className="eyebrow">최근 활동</span><h2>수집 실행 기록</h2></div><a href="./runs/">전체 실행 보기 →</a></div>
        <div className="table-wrap"><table><thead><tr><th>실행 ID</th><th>수집처</th><th>상태</th><th>성공</th><th>재시도 중</th><th>실패</th></tr></thead><tbody>{runs.map(run => <tr key={run.id}><td className="mono">{run.id.slice(0,18)}</td><td>{displayConnector(run.connector)}</td><td><span className={"status " + run.status}>{displayStatus(run.status)}</span></td><td>{run.succeeded.toLocaleString()}</td><td>{run.retrying}</td><td>{run.failed}</td></tr>)}</tbody></table></div>
      </section>
    </div>
  );
}
