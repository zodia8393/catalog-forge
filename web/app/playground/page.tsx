"use client";

import { useEffect, useRef, useState } from "react";
import { parseProductPreview, validatePreviewUrl, type PreviewResult, type PreviewSource } from "./parser";
import { PLAYGROUND_PRESETS, type PlaygroundPreset } from "./presets";

const MAX_HTML_LENGTH = 100_000;
const sourceLabels: Record<PreviewSource, string> = {
  generic: "Generic · JSON-LD / semantic fallback",
  books_to_scrape: "Books to Scrape · site selector",
};
const methodLabels: Record<string, string> = {
  json_ld: "JSON-LD",
  source_selector: "Site selector",
  semantic_fallback: "Semantic fallback",
  derived: "Derived",
};

export default function PlaygroundPage() {
  const initial = PLAYGROUND_PRESETS[0];
  const [activePreset, setActivePreset] = useState<string | null>(initial.id);
  const [source, setSource] = useState<PreviewSource>(initial.source);
  const [url, setUrl] = useState(initial.url);
  const [html, setHtml] = useState(initial.html);
  const [result, setResult] = useState<PreviewResult | null>(null);
  const [state, setState] = useState<"idle" | "parsing" | "ready" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const revision = useRef(0);

  useEffect(() => {
    const currentRevision = ++revision.current;
    const urlError = validatePreviewUrl(url);
    if (!html.trim()) {
      setResult(null);
      setError("HTML을 입력하면 결과가 이곳에 표시됩니다.");
      setState("idle");
      return;
    }
    if (html.length > MAX_HTML_LENGTH) {
      setResult(null);
      setError(`브라우저 보호를 위해 HTML은 ${MAX_HTML_LENGTH.toLocaleString()}자까지 처리합니다.`);
      setState("error");
      return;
    }
    if (urlError) {
      setResult(null);
      setError(urlError);
      setState("error");
      return;
    }

    setState("parsing");
    setError(null);
    const timer = window.setTimeout(() => {
      parseProductPreview(html, url, source)
        .then(preview => {
          if (revision.current !== currentRevision) return;
          setResult(preview);
          setState("ready");
        })
        .catch(cause => {
          if (revision.current !== currentRevision) return;
          setResult(null);
          setError(cause instanceof Error ? cause.message : "HTML을 파싱하지 못했습니다.");
          setState("error");
        });
    }, 180);
    return () => window.clearTimeout(timer);
  }, [html, source, url]);

  function applyPreset(preset: PlaygroundPreset) {
    setActivePreset(preset.id);
    setSource(preset.source);
    setUrl(preset.url);
    setHtml(preset.html);
  }

  async function copyResult() {
    if (!result?.product) return;
    await navigator.clipboard.writeText(JSON.stringify(result.product, null, 2));
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  const evidence = result ? Object.entries(result.evidence) : [];
  const confidence = result?.product?.confidence ?? 0;

  return (
    <div className="page playground-page">
      <header className="topbar">
        <div>
          <span className="eyebrow">실시간 체험 / 브라우저 파서</span>
          <h1>HTML을 바꾸면 상품 JSON이 바로 달라집니다</h1>
          <p>상품 HTML을 직접 붙여 넣고 CatalogForge의 추출 순서와 품질 판단을 실시간으로 확인하세요.</p>
        </div>
        <span className="mode live parser-live"><i /> LIVE PARSER</span>
      </header>

      <section className="playground-notice" aria-label="실시간 체험 안내">
        <div><strong>입력은 브라우저 안에서만 처리됩니다.</strong><span>HTML과 URL을 server로 보내거나 DB에 저장하지 않습니다.</span></div>
        <div><strong>URL을 대신 수집하지는 않습니다.</strong><span>공개 proxy의 CORS·SSRF·약관 위험 없이 parsing 자체를 체험하는 화면입니다.</span></div>
      </section>

      <section className="preset-section" aria-labelledby="preset-title">
        <div className="section-inline-head"><div><span className="eyebrow">빠른 시작</span><h2 id="preset-title">실행 예시를 불러오거나 직접 수정하세요</h2></div><span>입력 변경 후 180ms debounce</span></div>
        <div className="preset-grid">
          {PLAYGROUND_PRESETS.map(preset => (
            <button
              aria-pressed={activePreset === preset.id}
              className={"preset-button " + (activePreset === preset.id ? "active" : "")}
              key={preset.id}
              onClick={() => applyPreset(preset)}
              type="button"
            >
              <span>{preset.label}</span>
              <small>{preset.description}</small>
            </button>
          ))}
        </div>
      </section>

      <div className="playground-grid">
        <section className="panel playground-input">
          <div className="panel-head">
            <div><span className="eyebrow">입력</span><h2>수집된 상품 문서</h2></div>
            <span className={"parser-state " + state} aria-live="polite"><i />{state === "parsing" ? "분석 중" : state === "ready" ? "결과 갱신됨" : state === "error" ? "입력 확인" : "입력 대기"}</span>
          </div>
          <div className="input-controls">
            <label>
              <span>Source profile</span>
              <select value={source} onChange={event => { setActivePreset(null); setSource(event.target.value as PreviewSource); }}>
                {Object.entries(sourceLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label>
              <span>Page URL context</span>
              <input aria-invalid={Boolean(validatePreviewUrl(url))} onChange={event => { setActivePreset(null); setUrl(event.target.value); }} spellCheck={false} type="url" value={url} />
            </label>
          </div>
          <label className="html-input-label" htmlFor="playground-html">
            <span>HTML input</span>
            <small>{html.length.toLocaleString()} / {MAX_HTML_LENGTH.toLocaleString()}자</small>
          </label>
          <textarea
            id="playground-html"
            onChange={event => { setActivePreset(null); setHtml(event.target.value); }}
            spellCheck={false}
            value={html}
          />
          <div className="parser-order"><span>1</span> JSON-LD <i>→</i><span>2</span> site selector <i>→</i><span>3</span> semantic fallback</div>
        </section>

        <section className="panel playground-result" aria-live="polite" aria-busy={state === "parsing"}>
          <div className="panel-head">
            <div><span className="eyebrow">실시간 결과</span><h2>정규화 Product preview</h2></div>
            {result?.product && <button className="copy-button" onClick={copyResult} type="button">{copied ? "복사됨 ✓" : "JSON 복사"}</button>}
          </div>

          {error && <div className={"playground-empty " + (state === "error" ? "error" : "")}><strong>{state === "error" ? "입력을 확인해 주세요" : "HTML 입력 대기"}</strong><span>{error}</span></div>}
          {!error && state === "parsing" && <div className="playground-empty"><strong>입력 내용을 분석하고 있습니다</strong><span>DOM fingerprint와 field evidence를 계산합니다.</span></div>}
          {!error && result && (
            <>
              <div className="preview-metrics">
                <article><span>필수 필드</span><strong>{Math.round(result.required_field_coverage * 4)} / 4</strong><small>{(result.required_field_coverage * 100).toFixed(0)}% coverage</small></article>
                <article><span>Confidence</span><strong>{(confidence * 100).toFixed(1)}%</strong><small>field evidence 평균</small></article>
                <article><span>추출 경로</span><strong>{result.product?.extraction_path.length || 0}단계</strong><small>{result.product?.extraction_path.map(item => methodLabels[item]).join(" + ") || "추출 실패"}</small></article>
                <article><span>DOM fingerprint</span><strong className="mono">{result.dom_fingerprint}</strong><small>문서 구조 요약</small></article>
              </div>
              <div className={"preview-decision " + result.decision.status}>
                <div><span>품질 gate 판단</span><strong>{result.decision.label}</strong></div>
                <p>{result.decision.reason}</p>
              </div>
              <pre className="preview-json"><code>{JSON.stringify(result.product || { warnings: result.warnings }, null, 2)}</code></pre>
            </>
          )}
        </section>
      </div>

      {result && evidence.length > 0 && (
        <section className="panel live-evidence">
          <div className="panel-head"><div><span className="eyebrow">실시간 field evidence</span><h2>입력값을 바꾸면 아래 근거도 함께 갱신됩니다</h2></div><span className="run-id">{evidence.length} fields</span></div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>필드</th><th>추출 값</th><th>추출 방식</th><th>selector</th><th>신뢰도</th></tr></thead>
              <tbody>{evidence.map(([field, item]) => <tr key={field}><td className="mono">{field}</td><td>{item.value}</td><td><span className="source-pill evidence-method">{methodLabels[item.source]}</span></td><td className="mono">{item.selector}</td><td><strong>{(item.confidence * 100).toFixed(0)}%</strong></td></tr>)}</tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
