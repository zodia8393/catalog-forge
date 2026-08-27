from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable
from urllib.parse import urljoin
from uuid import UUID

from bs4 import BeautifulSoup, Tag

from .models import EvidenceSource, FieldEvidence, ParseOutcome, ProductRecord


_PRICE_RE = re.compile(r"(?P<currency>[$£€₩])?\s*(?P<amount>\d[\d,]*(?:\.\d{1,2})?)")
_CURRENCY_SYMBOLS = {"$": "USD", "£": "GBP", "€": "EUR", "₩": "KRW"}
_REQUIRED_FIELDS = ("title", "price_amount", "currency", "availability")


def _dom_fingerprint(soup: BeautifulSoup) -> str:
    signatures: Counter[str] = Counter()
    for tag in soup.find_all(True):
        classes = ".".join(sorted(tag.get("class", []))[:3])
        signatures[f"{tag.name}.{classes}" if classes else tag.name] += 1
    payload = "|".join(f"{key}:{count}" for key, count in sorted(signatures.items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _iter_json_ld(soup: BeautifulSoup) -> Iterable[dict[str, Any]]:
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(node.get_text(strip=True))
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            graph = candidate.get("@graph")
            if isinstance(graph, list):
                candidates.extend(item for item in graph if isinstance(item, dict))
            yield candidate


def _product_json_ld(soup: BeautifulSoup) -> dict[str, Any] | None:
    for candidate in _iter_json_ld(soup):
        raw_type = candidate.get("@type", "")
        types = raw_type if isinstance(raw_type, list) else [raw_type]
        if any(str(value).lower() == "product" for value in types):
            return candidate
    return None


def _parse_price(value: object, currency: str | None = None) -> tuple[Decimal | None, str | None]:
    if value is None:
        return None, currency
    match = _PRICE_RE.search(str(value).replace("\u00a0", " "))
    if not match:
        return None, currency
    try:
        amount = Decimal(match.group("amount").replace(",", ""))
    except InvalidOperation:
        return None, currency
    symbol_currency = _CURRENCY_SYMBOLS.get(match.group("currency") or "")
    return amount, (currency or symbol_currency)


def _text(node: Tag | None) -> str | None:
    return node.get_text(" ", strip=True) if node else None


def _record(
    evidence: dict[str, FieldEvidence],
    name: str,
    value: object,
    source: EvidenceSource,
    confidence: float,
    selector: str | None = None,
) -> None:
    if value in (None, "", []):
        return
    evidence[name] = FieldEvidence(
        value=value,
        source=source,
        confidence=confidence,
        selector=selector,
    )


def parse_product(
    *,
    html: str,
    url: str,
    run_id: UUID,
    target_id: UUID,
    source: str,
) -> ParseOutcome:
    soup = BeautifulSoup(html, "html.parser")
    fingerprint = _dom_fingerprint(soup)
    evidence: dict[str, FieldEvidence] = {}
    warnings: list[str] = []

    json_product = _product_json_ld(soup)
    if json_product:
        offers = json_product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if not isinstance(offers, dict):
            offers = {}
        _record(evidence, "title", json_product.get("name"), EvidenceSource.JSON_LD, 0.99, "$.name")
        _record(evidence, "brand", _brand_name(json_product.get("brand")), EvidenceSource.JSON_LD, 0.98, "$.brand")
        _record(evidence, "category", json_product.get("category"), EvidenceSource.JSON_LD, 0.98, "$.category")
        _record(evidence, "image_url", _first_value(json_product.get("image")), EvidenceSource.JSON_LD, 0.98, "$.image")
        _record(evidence, "external_id", json_product.get("sku") or json_product.get("productID"), EvidenceSource.JSON_LD, 0.99, "$.sku")
        _record(evidence, "availability", _availability(offers.get("availability")), EvidenceSource.JSON_LD, 0.98, "$.offers.availability")
        amount, currency = _parse_price(offers.get("price"), offers.get("priceCurrency"))
        _record(evidence, "price_amount", amount, EvidenceSource.JSON_LD, 0.99, "$.offers.price")
        _record(evidence, "currency", currency, EvidenceSource.JSON_LD, 0.99, "$.offers.priceCurrency")

    if source == "books_to_scrape":
        _parse_books_to_scrape(soup, evidence)

    _generic_fallbacks(soup, url, evidence)
    canonical_url = _canonical_url(soup, url)
    external_id = str(evidence.get("external_id", FieldEvidence(value=canonical_url, source=EvidenceSource.DERIVED, confidence=0.85)).value)
    title = str(evidence["title"].value) if "title" in evidence else ""
    if not title:
        warnings.append("missing_title")
        return ParseOutcome(
            product=None,
            required_field_coverage=_coverage(evidence),
            dom_fingerprint=fingerprint,
            warnings=warnings,
        )

    coverage = _coverage(evidence)
    confidence = sum(item.confidence for item in evidence.values()) / len(evidence)
    for field in _REQUIRED_FIELDS:
        if field not in evidence:
            warnings.append(f"missing_{field}")

    product = ProductRecord(
        run_id=run_id,
        target_id=target_id,
        source=source,
        external_id=external_id,
        canonical_url=canonical_url,
        title=title,
        price_amount=_decimal_value(evidence.get("price_amount")),
        currency=_string_value(evidence.get("currency")),
        availability=_string_value(evidence.get("availability")),
        brand=_string_value(evidence.get("brand")),
        category=_string_value(evidence.get("category")),
        image_url=urljoin(url, _string_value(evidence.get("image_url")) or "") or None,
        confidence=round(confidence, 4),
        dom_fingerprint=fingerprint,
        field_evidence=evidence,
    )
    return ParseOutcome(
        product=product,
        required_field_coverage=coverage,
        dom_fingerprint=fingerprint,
        warnings=warnings,
    )


def discover_product_links(html: str, base_url: str, source: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    selector = "article.product_pod h3 a" if source == "books_to_scrape" else 'a[data-product-url], a[rel="product"]'
    links: list[str] = []
    for node in soup.select(selector):
        href = node.get("href") or node.get("data-product-url")
        if href:
            absolute = urljoin(base_url, str(href))
            if absolute not in links:
                links.append(absolute)
    return links


def _parse_books_to_scrape(soup: BeautifulSoup, evidence: dict[str, FieldEvidence]) -> None:
    table = {
        _text(row.find("th")): _text(row.find("td"))
        for row in soup.select("table.table-striped tr")
    }
    _record(evidence, "title", _text(soup.select_one(".product_main h1")), EvidenceSource.SOURCE_SELECTOR, 0.97, ".product_main h1")
    _record(evidence, "external_id", table.get("UPC"), EvidenceSource.SOURCE_SELECTOR, 0.99, "table:UPC")
    _record(evidence, "category", table.get("Product Type"), EvidenceSource.SOURCE_SELECTOR, 0.96, "table:Product Type")
    _record(evidence, "availability", table.get("Availability") or _text(soup.select_one(".availability")), EvidenceSource.SOURCE_SELECTOR, 0.96, "table:Availability")
    price_text = table.get("Price (incl. tax)") or _text(soup.select_one(".price_color"))
    amount, currency = _parse_price(price_text)
    _record(evidence, "price_amount", amount, EvidenceSource.SOURCE_SELECTOR, 0.98, "table:Price (incl. tax)")
    _record(evidence, "currency", currency, EvidenceSource.SOURCE_SELECTOR, 0.98, "table:Price (incl. tax)")
    image = soup.select_one(".item.active img")
    _record(evidence, "image_url", image.get("src") if image else None, EvidenceSource.SOURCE_SELECTOR, 0.95, ".item.active img")


def _generic_fallbacks(soup: BeautifulSoup, url: str, evidence: dict[str, FieldEvidence]) -> None:
    if "title" not in evidence:
        node = soup.select_one('meta[property="og:title"]')
        title = node.get("content") if node else _text(soup.select_one("h1"))
        _record(evidence, "title", title, EvidenceSource.SEMANTIC_FALLBACK, 0.86, "og:title|h1")
    if "image_url" not in evidence:
        node = soup.select_one('meta[property="og:image"]')
        _record(evidence, "image_url", node.get("content") if node else None, EvidenceSource.SEMANTIC_FALLBACK, 0.85, "og:image")
    if "price_amount" not in evidence:
        node = soup.select_one('[itemprop="price"], meta[property="product:price:amount"], [data-price]')
        value = node.get("content") or node.get("data-price") or _text(node) if node else None
        currency_node = soup.select_one('[itemprop="priceCurrency"], meta[property="product:price:currency"]')
        currency_value = currency_node.get("content") if currency_node else None
        amount, currency = _parse_price(value, currency_value)
        _record(evidence, "price_amount", amount, EvidenceSource.SEMANTIC_FALLBACK, 0.84, "itemprop=price")
        _record(evidence, "currency", currency, EvidenceSource.SEMANTIC_FALLBACK, 0.84, "itemprop=priceCurrency")
    if "availability" not in evidence:
        node = soup.select_one('[itemprop="availability"], link[itemprop="availability"], [data-availability]')
        value = node.get("content") or node.get("href") or node.get("data-availability") or _text(node) if node else None
        _record(evidence, "availability", _availability(value), EvidenceSource.SEMANTIC_FALLBACK, 0.82, "itemprop=availability")
    evidence.setdefault("external_id", FieldEvidence(value=url, source=EvidenceSource.DERIVED, confidence=0.8, selector="canonical_url"))


def _canonical_url(soup: BeautifulSoup, url: str) -> str:
    node = soup.select_one('link[rel="canonical"]')
    return urljoin(url, str(node.get("href"))) if node and node.get("href") else url


def _brand_name(value: object) -> object:
    if isinstance(value, dict):
        return value.get("name")
    return value


def _first_value(value: object) -> object:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _availability(value: object) -> str | None:
    if value is None:
        return None
    return str(value).rsplit("/", 1)[-1].strip()


def _coverage(evidence: dict[str, FieldEvidence]) -> float:
    return sum(field in evidence for field in _REQUIRED_FIELDS) / len(_REQUIRED_FIELDS)


def _string_value(field: FieldEvidence | None) -> str | None:
    return str(field.value) if field and field.value is not None else None


def _decimal_value(field: FieldEvidence | None) -> Decimal | None:
    if not field or field.value is None:
        return None
    return Decimal(str(field.value))
