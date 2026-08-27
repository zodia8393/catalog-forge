import type { PreviewSource } from "./parser";

export type PlaygroundPreset = {
  id: string;
  label: string;
  description: string;
  source: PreviewSource;
  url: string;
  html: string;
};

export const PLAYGROUND_PRESETS: PlaygroundPreset[] = [
  {
    id: "books-selector",
    label: "공개 상품 HTML",
    description: "site selector로 4개 필드를 추출",
    source: "books_to_scrape",
    url: "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
    html: `<!doctype html>
<html>
  <head><link rel="canonical" href="/catalogue/a-light-in-the-attic_1000/index.html"></head>
  <body>
    <div class="product_main">
      <h1>A Light in the Attic</h1>
      <p class="price_color">£51.77</p>
      <p class="instock availability">In stock (22 available)</p>
    </div>
    <table class="table-striped">
      <tr><th>UPC</th><td>a897fe39b1053632</td></tr>
      <tr><th>Product Type</th><td>Books</td></tr>
      <tr><th>Price (excl. tax)</th><td>£51.77</td></tr>
      <tr><th>Price (incl. tax)</th><td>£51.77</td></tr>
      <tr><th>Tax</th><td>£0.00</td></tr>
      <tr><th>Availability</th><td>In stock (22 available)</td></tr>
    </table>
    <div class="item active"><img src="../../media/cache/sample.jpg" alt="A Light in the Attic"></div>
  </body>
</html>`,
  },
  {
    id: "json-ld",
    label: "JSON-LD 상품",
    description: "표준 schema.org 값을 우선 사용",
    source: "generic",
    url: "https://shop.example/products/120",
    html: `<!doctype html>
<html>
  <head>
    <link rel="canonical" href="/products/120">
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Product",
      "sku": "SKU-120",
      "name": "Recovered Product 120",
      "brand": {"@type": "Brand", "name": "Forge Labs"},
      "category": "Fixture",
      "image": "/images/120.jpg",
      "offers": {
        "@type": "Offer",
        "price": "19.90",
        "priceCurrency": "USD",
        "availability": "https://schema.org/InStock"
      }
    }
    </script>
  </head>
  <body><h1>Recovered Product 120</h1></body>
</html>`,
  },
  {
    id: "semantic-fallback",
    label: "구조 변경 HTML",
    description: "semantic metadata로 복구 후 검수",
    source: "generic",
    url: "https://shop.example/products/91?variant=drift",
    html: `<!doctype html>
<html>
  <head>
    <meta property="og:title" content="Redesigned Product 91">
    <link rel="canonical" href="/products/91">
  </head>
  <body>
    <main class="redesigned-card">
      <data itemprop="price" value="21.90" content="21.90"></data>
      <meta itemprop="priceCurrency" content="USD">
      <span data-availability="InStock"></span>
    </main>
  </body>
</html>`,
  },
];
