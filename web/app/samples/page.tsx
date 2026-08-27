"use client";

import { useState } from "react";
import sampleDataset from "../../public/sample-products.json";

export default function SamplesPage() {
  const [selectedId, setSelectedId] = useState(sampleDataset.cases[0].id);
  const sample = sampleDataset.cases.find(item => item.id === selectedId) ?? sampleDataset.cases[0];

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <span className="eyebrow">샘플 데이터 / 입력부터 결과까지</span>
          <h1>상품 페이지가 어떤 데이터로 바뀌는지 확인하세요</h1>
          <p>정상 수집, 요청 실패 복구, 사이트 구조 변경까지 세 가지 대표 흐름을 실제 값으로 연결했습니다.</p>
        </div>
        <a className="download-link" href="../sample-products.json" download>샘플 JSON 내려받기</a>
      </header>

      <section className="demo-note" aria-label="샘플 데이터 안내">
        <strong>공개 sandbox 1건과 프로젝트가 만든 합성 장애 표본 2건입니다.</strong>
        <span>각 탭에서 원본 입력, 처리 단계, 최종 JSON, 필드별 추출 근거를 확인할 수 있습니다.</span>
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
