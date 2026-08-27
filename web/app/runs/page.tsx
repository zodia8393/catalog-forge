import Link from "next/link";
import {
  displayConnector,
  displayStatus,
  formatDuration,
  formatKst,
  recordedAt,
  replayRuns,
  replayTimeline,
  runTargetCount,
} from "../data";

export default function RunsPage() {
  return (
    <div className="page">
      <header className="topbar">
        <div>
          <span className="eyebrow">운영 현황 / 수집 실행</span>
          <h1>실패를 숨기지 않고 상태로 관리합니다</h1>
          <p>각 수집 대상이 대기, 처리, 재시도, 성공, 실패 중 어디에 있는지 기록합니다.</p>
        </div>
        <div className="top-actions"><span className="mode recorded">실제 실행 snapshot</span><Link className="action-link" href="/samples/">attempt 근거 보기 <span>→</span></Link></div>
      </header>
      <section className="demo-note" aria-label="표 읽는 방법">
        <strong>{recordedAt} KST 실제 실행 결과</strong>
        <span>UUID, 생성 시각, 상태별 건수는 generator가 pipeline DB에서 읽어 기록한 값입니다.</span>
      </section>
      <section className="panel">
        <div className="table-wrap">
          <table>
            <thead><tr><th>실행 ID</th><th>수집처</th><th>시작 (KST)</th><th>소요</th><th>상태</th><th>대상</th><th>성공</th><th>실패·차단</th></tr></thead>
            <tbody>{replayRuns.map(run => <tr key={run.id}><td className="mono run-cell" title={run.id}>{run.id}</td><td>{displayConnector(run.connector)}</td><td>{formatKst(run.created_at)}</td><td>{formatDuration(run)}</td><td><span className={"status " + run.status}>{displayStatus(run.status)}</span></td><td>{runTargetCount(run).toLocaleString()}</td><td>{run.succeeded.toLocaleString()}</td><td>{run.failed + run.blocked}</td></tr>)}</tbody>
          </table>
        </div>
      </section>
      <section className="panel trace-panel">
        <div className="panel-head">
          <div><span className="eyebrow">선택한 실제 실행</span><h2 className="mono run-title">{replayRuns[0].id}</h2></div>
          <span className="healthy">복구 완료</span>
        </div>
        <ol className="timeline horizontal">{replayTimeline.map((item,index)=><li key={item.time}><span className={index===replayTimeline.length-1?"done":""}/><time>{item.time}</time><div><strong>{item.event}</strong><small>{item.detail}</small></div></li>)}</ol>
      </section>
    </div>
  );
}
