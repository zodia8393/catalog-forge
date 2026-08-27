"use client";

import { useState } from "react";
import sampleDataset from "../../public/sample-products.json";
import { recordedAt, recordedCommand } from "../data";

const environmentLabels: Record<string, string> = {
  external_network: "외부 공개 sandbox",
  local_asgi_fault_injection: "로컬 ASGI 장애 주입",
  local_asgi_drift_injection: "로컬 ASGI 구조 변경 주입",
};

export default function SamplesPage() {
  const [selectedId, setSelectedId] = useState(sampleDataset.cases[0].id);
  const sample = sampleDataset.cases.find(item => item.id === selectedId) ?? sampleDataset.cases[0];

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <span className="eyebrow">샘플 데이터 / 입력부터 결과까지</span>
          <h1>상품 페이지가 어떤 데이터로 바뀌는지 확인하세요</h1>
          <p>외부 수집, 429 복구, 구조 변경 감지를 실제로 실행한 입력·DB 기록·결과를 연결했습니다.</p>
        </div>
        <a className="download-link" href="../sample-products.json" download>실제 실행 JSON 내려받기</a>
      </header>

      <section className="demo-note" aria-label="샘플 데이터 안내">
        <strong>세 탭 모두 실제 pipeline 실행 기록입니다.</strong>
        <span>{recordedAt} KST 생성 · 외부 sandbox 1회 + 로컬 장애·구조 변경 주입 2회</span>
      </section>

      <section className="provenance" aria-label="데이터 생성 방법">
        <span className="actual-badge"><i /> ACTUAL RUN</span>
        <div><strong>재생용 예시를 손으로 입력하지 않았습니다.</strong><small>아래 명령이 run UUID, attempt, product, review와 응답 hash를 수집해 이 화면의 JSON을 생성했습니다.</small></div>
        <code>{recordedCommand}</code>
      </section>

      <div className="sample-tabs" role="tablist" aria-label="샘플 유형">
        {sampleDataset.cases.map(item => (
          <button
            aria-controls="sample-detail"
            aria-selected={item.id === sample.id}
            className={"sample-tab " + item.tone + (item.id === sample.id ? " active" : "")}
            key={item.id}
            onClick={() => setSelectedId(item.id)}
            role="tab"
            type="button"
          >
            <span>{item.kind}</span>
            <strong>{item.label}</strong>
            <small>{item.short_description}</small>
          </button>
        ))}
      </div>

      <section className="sample-detail" id="sample-detail" role="tabpanel">
        <div className="sample-detail-head">
          <div>
            <span className="eyebrow">{sample.kind}</span>
            <h2>{sample.label}</h2>
            <p>{sample.description}</p>
          </div>
          <div className={"decision " + sample.decision.status}>
            <span>최종 판단</span>
            <strong>{sample.decision.label}</strong>
            <small>{sample.decision.reason}</small>
          </div>
        </div>

        <section className="execution-proof" aria-label="실행 증거">
          <div><span>실행 여부</span><strong><i /> 실제 실행 완료</strong></div>
          <div><span>실행 환경</span><strong>{environmentLabels[sample.execution.environment] ?? sample.execution.environment}</strong></div>
          <div><span>run UUID</span><code title={sample.execution.run_id}>{sample.execution.run_id}</code></div>
          <div><span>pipeline HTTP 상태</span><strong>{sample.execution.request_statuses.join(" → ")}</strong></div>
          <div><span>응답 SHA-256</span><code title={sample.execution.response_sha256}>{sample.execution.response_sha256}</code></div>
        </section>

        <section className="sample-flow" aria-label="처리 단계">
          {sample.steps.map((step, index) => (
            <article key={step.title}>
              <span>{index + 1}</span>
              <strong>{step.title}</strong>
              <small>{step.detail}</small>
            </article>
          ))}
        </section>

        <div className="sample-grid">
          <section className="sample-code-panel">
            <div className="code-panel-head">
              <div><span className="eyebrow">입력 데이터</span><h3>{sample.input.source_label}</h3></div>
              <span>{sample.input.format}</span>
            </div>
            <code className="sample-url">{sample.input.url}</code>
            <pre><code>{sample.input.raw}</code></pre>
          </section>

          <section className="sample-code-panel output">
            <div className="code-panel-head">
              <div><span className="eyebrow">정규화 결과</span><h3>Product record</h3></div>
              <span>JSON</span>
            </div>
            <pre><code>{JSON.stringify(sample.output, null, 2)}</code></pre>
          </section>
        </div>

        <section className="panel evidence-panel">
          <div className="panel-head">
            <div><span className="eyebrow">핵심 필드별 근거</span><h2>이 값이 어디서 왔는지 추적</h2></div>
            <span className="run-id">confidence 0–1</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>필드</th><th>추출 값</th><th>추출 방식</th><th>selector</th><th>신뢰도</th></tr></thead>
              <tbody>
                {sample.evidence.map(item => (
                  <tr key={item.field}>
                    <td className="mono">{item.field}</td>
                    <td>{item.value}</td>
                    <td><span className="source-pill evidence-method">{item.method}</span></td>
                    <td className="mono">{item.selector}</td>
                    <td><strong>{(item.confidence * 100).toFixed(0)}%</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </section>
    </div>
  );
}
