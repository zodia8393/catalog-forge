import { replayProducts } from "../data";

export default function ProductsPage() {
  return <div className="page"><header className="topbar"><div><span className="eyebrow">CATALOG / PRODUCTS</span><h1>Evidence-backed product records</h1><p>값뿐 아니라 추출 source, confidence, DOM fingerprint를 함께 보존합니다.</p></div><span className="mode replay">4 REPLAY RECORDS</span></header>
    <section className="metrics"><article className="metric good"><span>High confidence</span><strong>3</strong><small>confidence ≥ 0.90</small></article><article className="metric warn"><span>Human review</span><strong>1</strong><small>schema drift fallback</small></article><article className="metric"><span>Required coverage</span><strong>100%</strong><small>title · price · currency · stock</small></article><article className="metric"><span>Duplicate snapshots</span><strong>0</strong><small>source + external ID boundary</small></article></section>
    <section className="catalog-grid">{replayProducts.map(product => <article className="product-card" key={product.id}><div className="product-top"><span className={`confidence ${product.confidence < .9 ? "review" : ""}`}>{(product.confidence*100).toFixed(1)}%</span><span className="source-pill">{product.source}</span></div><h2>{product.title}</h2><strong className="price">{product.currency} {product.price_amount}</strong><p>{product.availability}</p><footer><span>DOM fingerprint</span><code>{product.dom_fingerprint}</code></footer></article>)}</section>
  </div>;
}
