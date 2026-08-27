from decimal import Decimal
from uuid import uuid4

from catalog_forge.fixture_app import (
    _drift_product,
    _json_ld_product,
    _selector_product,
    _semantic_body,
)
from catalog_forge.models import EvidenceSource
from catalog_forge.parser import discover_product_links, parse_product


def parse(html: str, source: str = "generic"):
    return parse_product(
        html=html,
        url="http://fixture/products/7",
        run_id=uuid4(),
        target_id=uuid4(),
        source=source,
    )


def test_json_ld_is_preferred_and_preserves_evidence() -> None:
    outcome = parse(_json_ld_product(7, "Reliable Product 7", "17.90"))

    assert outcome.required_field_coverage == 1.0
    assert outcome.product is not None
    assert outcome.product.external_id == "SKU-7"
    assert outcome.product.price_amount == Decimal("17.90")
    assert outcome.product.currency == "USD"
    assert outcome.product.field_evidence["title"].source == EvidenceSource.JSON_LD
    assert len(outcome.dom_fingerprint) == 16


def test_source_adapter_handles_selector_only_page() -> None:
    outcome = parse(
        _selector_product(4, "Selector Product", "23.50"),
        source="books_to_scrape",
    )

    assert outcome.product is not None
    assert outcome.product.external_id == "UPC-4"
    assert outcome.product.price_amount == Decimal("23.50")
    assert outcome.product.currency == "GBP"
    assert outcome.product.availability == "In stock (7 available)"


def test_semantic_fallback_survives_dom_drift() -> None:
    outcome = parse(_drift_product(9, "Redesigned Product", "31.20"))

    assert outcome.required_field_coverage == 1.0
    assert outcome.product is not None
    assert outcome.product.title == "Redesigned Product"
    assert outcome.product.price_amount == Decimal("31.20")
    assert outcome.product.field_evidence["title"].source == EvidenceSource.SEMANTIC_FALLBACK


def test_malformed_json_ld_falls_back_without_crashing() -> None:
    html = '<script type="application/ld+json">{broken</script>' + _semantic_body("Fallback Product", "12.00")
    outcome = parse(html)

    assert outcome.product is not None
    assert outcome.product.title == "Fallback Product"
    assert outcome.required_field_coverage == 1.0


def test_labeled_fixture_required_field_accuracy_is_100_percent() -> None:
    correct = 0
    total = 0
    for product_id in range(1, 101):
        expected_price = Decimal(f"{10 + product_id % 80}.90")
        outcome = parse(_json_ld_product(product_id, f"Reliable Product {product_id}", str(expected_price)))
        assert outcome.product is not None
        checks = [
            outcome.product.title == f"Reliable Product {product_id}",
            outcome.product.price_amount == expected_price,
            outcome.product.currency == "USD",
            outcome.product.availability == "InStock",
        ]
        correct += sum(checks)
        total += len(checks)

    assert correct == total == 400


def test_connector_discovers_unique_absolute_product_links() -> None:
    html = '''<article class="product_pod"><h3><a href="../one.html">One</a></h3></article>
    <article class="product_pod"><h3><a href="../one.html">Duplicate</a></h3></article>
    <article class="product_pod"><h3><a href="../two.html">Two</a></h3></article>'''

    assert discover_product_links(
        html,
        "https://books.toscrape.com/catalogue/page-1.html",
        "books_to_scrape",
    ) == [
        "https://books.toscrape.com/one.html",
        "https://books.toscrape.com/two.html",
    ]
