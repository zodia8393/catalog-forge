import {
  displayAvailability,
  displayConnector,
  replayProducts,
} from "../data";

export default function ProductsPage() {
  return (
    <div className="page">
      <header className="topbar">
        <div>
          <span className="eyebrow">상품 데이터 / 품질 검수</span>
          <h1>상품 값마다 근거와 신뢰도를 남깁니다</h1>
          <p>추출한 값뿐 아니라 원본 수집처, 신뢰도, 문서 구조 지문을 함께 보존합니다.</p>
        </div>
        <span className="mode replay">재생 기록 4건</span>
      </header>
      <section className="demo-note" aria-label="검수 안내">
        <strong>신뢰도가 낮거나 구조가 바뀐 상품은 자동 저장하지 않습니다.</strong>
        <span>별도 검수 대상으로 분리해 잘못된 가격이나 재고가 상품 catalog를 오염시키는 일을 막습니다.</span>
      </section>
      <section className="metrics">
        <article className="metric good"><span>높은 신뢰도</span><strong>3건</strong><small>신뢰도 90% 이상</small></article>
        <article className="metric warn"><span>사람 검수 필요</span><strong>1건</strong><small>문서 구조 변경 감지</small></article>
        <article className="metric"><span>필수 필드 확보율</span><strong>100%</strong><small>제목 · 가격 · 통화 · 재고</small></article>
        <article className="metric"><span>중복 저장</span><strong>0건</strong><small>수집처 + 외부 상품 ID 기준</small></article>
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
            <footer><span>문서 구조 지문 (DOM fingerprint)</span><code>{product.dom_fingerprint}</code></footer>
          </article>
        ))}
      </section>
    </div>
  );
}
