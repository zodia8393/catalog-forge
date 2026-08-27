import {
  displayAvailability,
  displayConnector,
  recordedMetrics,
  replayProducts,
} from "../data";

export default function ProductsPage() {
  const highConfidence = replayProducts.filter(product => product.confidence >= .9).length;
  const reviewRequired = replayProducts.filter(product => product.review_required).length;

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <span className="eyebrow">상품 데이터 / 품질 검수</span>
          <h1>상품 값마다 근거와 신뢰도를 남깁니다</h1>
          <p>추출한 값뿐 아니라 원본 수집처, 신뢰도, 문서 구조 지문을 함께 보존합니다.</p>
        </div>
        <span className="mode replay">실제 저장 기록 {replayProducts.length}건</span>
      </header>
      <section className="demo-note" aria-label="검수 안내">
        <strong>실제 pipeline DB에서 선택한 product snapshot입니다.</strong>
        <span>외부 상품 1건, 정상·복구 fixture 2건, 구조 변경 검수 1건의 실제 UUID와 파싱 결과입니다.</span>
      </section>
      <section className="metrics">
        <article className="metric good"><span>높은 신뢰도</span><strong>{highConfidence}건</strong><small>신뢰도 90% 이상 실제 표본</small></article>
        <article className="metric warn"><span>사람 검수 필요</span><strong>{reviewRequired}건</strong><small>실제 schema_drift review</small></article>
        <article className="metric"><span>필수 필드 확보</span><strong>{recordedMetrics.required_fields_present}/{recordedMetrics.required_fields_expected}</strong><small>제목 · 가격 · 통화 · 재고</small></article>
        <article className="metric"><span>중복 저장</span><strong>{recordedMetrics.duplicate_snapshots}건</strong><small>1,000건 복구 run 재계산</small></article>
      </section>
      <section className="catalog-grid">
        {replayProducts.map(product => (
          <article className="product-card" key={product.id}>
            <div className="product-top">
              <span className={"confidence " + (product.confidence < .9 ? "review" : "")}>신뢰도 {(product.confidence*100).toFixed(1)}%</span>
              <span className="source-pill" title={product.source}>{displayConnector(product.source)}</span>
            </div>
            <h2>{product.title}</h2>
            <strong className="price">{product.currency} {product.price_amount}</strong>
            <p className="availability">재고 상태 · {displayAvailability(product.availability)}</p>
            <footer><span>실제 product UUID</span><code>{product.id}</code><span className="fingerprint-label">문서 구조 지문</span><code>{product.dom_fingerprint}</code></footer>
          </article>
        ))}
      </section>
    </div>
  );
}
