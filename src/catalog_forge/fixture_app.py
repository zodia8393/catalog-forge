from __future__ import annotations

import asyncio
from collections import defaultdict
from html import escape

from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, PlainTextResponse


app = FastAPI(title="CatalogForge deterministic commerce fixture")
_attempts: defaultdict[str, int] = defaultdict(int)


@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots() -> str:
    return "User-agent: *\nDisallow: /blocked\nAllow: /\n"


@app.get("/catalog", response_class=HTMLResponse)
async def catalog(count: int = 20) -> str:
    links = "".join(
        f'<article class="product_pod"><h3><a href="/products/{index}">Product {index}</a></h3></article>'
        for index in range(1, min(count, 1000) + 1)
    )
    return f"<html><body>{links}</body></html>"


@app.get("/products/{product_id}", response_class=HTMLResponse)
async def product(product_id: int, variant: str = "jsonld", delay_ms: int = 0) -> str:
    if delay_ms:
        await asyncio.sleep(min(max(delay_ms, 0), 1000) / 1000)
    title = f"Reliable Product {product_id}"
    price = f"{10 + product_id % 80}.90"
    if variant == "selector":
        return _selector_product(product_id, title, price)
    if variant == "drift":
        return _drift_product(product_id, title, price)
    if variant == "missing":
        return f'<html><head><link rel="canonical" href="/products/{product_id}"></head><body><h1>{escape(title)}</h1></body></html>'
    if variant == "malformed":
        return f'<html><head><script type="application/ld+json">{{broken</script></head><body>{_semantic_body(title, price)}</body></html>'
    return _json_ld_product(product_id, title, price)


@app.get("/dynamic/{product_id}", response_class=HTMLResponse)
async def dynamic_product(product_id: int) -> str:
    title = escape(f"Dynamic Product {product_id}")
    script = (
        "document.body.innerHTML='<h1>" + title + "</h1>"
        "<span itemprop=\"price\" content=\"29.90\"></span>"
        "<meta itemprop=\"priceCurrency\" content=\"USD\">"
        "<link itemprop=\"availability\" href=\"https://schema.org/InStock\">';"
    )
    return f"<html><body><div id='loading'>Loading</div><script>{script}</script></body></html>"


@app.get("/unstable/{product_id}", response_class=HTMLResponse)
async def unstable(product_id: int, failures: int = 2) -> Response:
    key = f"{product_id}:{failures}"
    _attempts[key] += 1
    if _attempts[key] <= failures:
        return HTMLResponse("retry later", status_code=429, headers={"Retry-After": "0"})
    return HTMLResponse(_json_ld_product(product_id, f"Recovered Product {product_id}", "19.90"))


@app.post("/fixture/reset")
async def reset_fixture() -> dict[str, bool]:
    _attempts.clear()
    return {"reset": True}


def _json_ld_product(product_id: int, title: str, price: str) -> str:
    return f'''<!doctype html><html><head>
<link rel="canonical" href="/products/{product_id}">
<script type="application/ld+json">{{
  "@context":"https://schema.org","@type":"Product","sku":"SKU-{product_id}",
  "name":"{escape(title)}","brand":{{"@type":"Brand","name":"Forge Labs"}},
  "category":"Fixture","image":"/images/{product_id}.jpg",
  "offers":{{"@type":"Offer","price":"{price}","priceCurrency":"USD","availability":"https://schema.org/InStock"}}
}}</script></head><body><h1>{escape(title)}</h1></body></html>'''


def _selector_product(product_id: int, title: str, price: str) -> str:
    return f'''<html><head><link rel="canonical" href="/products/{product_id}"></head><body>
<div class="product_main"><h1>{escape(title)}</h1><p class="price_color">£{price}</p><p class="availability">In stock</p></div>
<table class="table-striped"><tr><th>UPC</th><td>UPC-{product_id}</td></tr><tr><th>Product Type</th><td>Fixture</td></tr><tr><th>Price (incl. tax)</th><td>£{price}</td></tr><tr><th>Availability</th><td>In stock (7 available)</td></tr></table>
<div class="item active"><img src="/images/{product_id}.jpg"></div></body></html>'''


def _drift_product(product_id: int, title: str, price: str) -> str:
    return f'''<html><head><meta property="og:title" content="{escape(title)}"><link rel="canonical" href="/products/{product_id}"></head>
<body><main class="redesigned-card"><data itemprop="price" value="{price}" content="{price}"></data><meta itemprop="priceCurrency" content="USD"><span data-availability="InStock"></span></main></body></html>'''


def _semantic_body(title: str, price: str) -> str:
    return f'<h1>{escape(title)}</h1><data itemprop="price" content="{price}"></data><meta itemprop="priceCurrency" content="USD"><span data-availability="InStock"></span>'


def main() -> None:
    import uvicorn

    uvicorn.run("catalog_forge.fixture_app:app", host="0.0.0.0", port=8101, reload=False)


if __name__ == "__main__":
    main()
