from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from .config import Settings
from .fetcher import HttpFetcher
from .models import CrawlRunCreate, CrawlRunSummary
from .parser import discover_product_links
from .queueing import InMemoryQueue, OutboxPublisher
from .service import TargetProcessor
from .storage import Store


@dataclass(slots=True)
class BooksDemoExecution:
    report: dict[str, Any]
    run: CrawlRunSummary
    products: list[dict[str, Any]] = field(default_factory=list)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    sample_response: dict[str, Any] = field(default_factory=dict)


async def execute_books_demo(product_limit: int, *, capture: bool = False) -> BooksDemoExecution:
    settings = Settings(
        database_url="sqlite:///:memory:",
        allowed_hosts=["books.toscrape.com"],
        max_concurrency_per_host=4,
        min_host_interval_ms=150,
        max_attempts=3,
    )
    fetcher = HttpFetcher(
        allowed_hosts=settings.allowed_hosts,
        max_concurrency_per_host=settings.max_concurrency_per_host,
        min_host_interval_seconds=settings.min_host_interval_ms / 1000,
        enforce_robots=True,
    )
    product_urls: list[str] = []
    listing_pages = 0
    started = time.perf_counter()
    captured_products: list[dict[str, Any]] = []
    captured_attempts: list[dict[str, Any]] = []
    sample_response: dict[str, Any] = {}
    try:
        while len(product_urls) < product_limit:
            listing_pages += 1
            listing_url = f"https://books.toscrape.com/catalogue/page-{listing_pages}.html"
            listing = await fetcher.fetch(listing_url)
            discovered = discover_product_links(listing.text, listing.final_url, "books_to_scrape")
            if not discovered:
                break
            for url in discovered:
                if url not in product_urls:
                    product_urls.append(url)
            if listing_pages >= 50:
                break

        product_urls = product_urls[:product_limit]
        if not product_urls:
            raise RuntimeError("Books to Scrape discovery returned no product URLs")
        store = Store(settings.database_url)
        store.init_schema()
        run = store.create_run(
            CrawlRunCreate(
                connector="books_to_scrape",
                start_urls=product_urls,
                max_pages=len(product_urls),
                render_mode="http",
            ),
            max_attempts=settings.max_attempts,
        )
        queue = InMemoryQueue()
        publisher = OutboxPublisher(store, queue)
        while await publisher.publish_due():
            pass
        processor = TargetProcessor(store, fetcher, settings)
        while True:
            batch = await queue.read("public-demo", count=20, block_ms=10)
            if not batch:
                break
            results = await asyncio.gather(*(processor.process(item.payload) for item in batch))
            for item in batch:
                await queue.ack(item.message_id)
            if any(result == "retrying" for result in results):
                while await publisher.publish_due():
                    pass
        summary = store.get_run(run.id)
        metrics = store.metrics()
        if summary is None:
            raise RuntimeError("public demo run disappeared")
        if capture:
            product_rows = store.list_products(source="books_to_scrape", limit=product_limit)
            product = next(
                (row for row in product_rows if row["canonical_url"] == product_urls[0]),
                None,
            )
            if product is None:
                raise RuntimeError("captured public product could not be found")
            captured_products.append(product)
            captured_attempts = store.list_fetch_attempts(
                target_id=UUID(product["target_id"]),
                limit=settings.max_attempts,
            )
            response = await fetcher.fetch(product_urls[0])
            sample_response = {
                "url": response.final_url,
                "status_code": response.status_code,
                "html": response.text,
                "bytes_received": response.bytes_received,
            }
        report: dict[str, int | float | str] = {
            "run_id": str(run.id),
            "listing_pages": listing_pages,
            "discovered_product_urls": len(product_urls),
            "succeeded": summary.succeeded,
            "failed": summary.failed,
            "blocked": summary.blocked,
            "fetch_attempts": metrics["attempts"],
            "product_snapshots": metrics["products"],
            "success_rate": round(summary.succeeded / len(product_urls), 4),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
        return BooksDemoExecution(
            report=report,
            run=summary,
            products=captured_products,
            attempts=captured_attempts,
            sample_response=sample_response,
        )
    finally:
        await fetcher.close()


async def run_books_demo(product_limit: int) -> dict[str, Any]:
    return (await execute_books_demo(product_limit)).report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the allowlisted Books to Scrape connector demo")
    parser.add_argument("--products", type=int, default=20)
    parser.add_argument("--output-root", type=Path, default=Path(os.environ.get("OUTPUT_ROOT", "artifacts")))
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    report = asyncio.run(run_books_demo(args.products))
    output = args.output_root / "books_to_scrape_demo.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
