import { replayRuns, replayTimeline } from "../data";

export default function RunsPage() {
  return <div className="page"><header className="topbar"><div><span className="eyebrow">OPERATIONS / CRAWL RUNS</span><h1>Failure is a state, not a surprise</h1><p>각 target의 retry, block, terminal 상태를 재현 가능한 evidence로 남깁니다.</p></div><button className="primary">+ New crawl run</button></header>
    <section className="panel"><div className="table-wrap"><table><thead><tr><th>RUN ID</th><th>CONNECTOR</th><th>STATE</th><th>QUEUED</th><th>RUNNING</th><th>RETRYING</th><th>SUCCEEDED</th><th>FAILED</th></tr></thead><tbody>{replayRuns.map(run => <tr key={run.id}><td className="mono">{run.id}</td><td>{run.connector}</td><td><span className={`status ${run.status}`}>{run.status}</span></td><td>{run.queued}</td><td>{run.running}</td><td>{run.retrying}</td><td>{run.succeeded}</td><td>{run.failed}</td></tr>)}</tbody></table></div></section>
    <section className="panel trace-panel"><div className="panel-head"><div><span className="eyebrow">SELECTED RUN</span><h2>run-chaos-1000</h2></div><span className="healthy">Recovery complete</span></div><ol className="timeline horizontal">{replayTimeline.map((item,index)=><li key={item.time}><span className={index===replayTimeline.length-1?"done":""}/><time>{item.time}</time><div><strong>{item.event}</strong><small>{item.detail}</small></div></li>)}</ol></section>
  </div>;
}
