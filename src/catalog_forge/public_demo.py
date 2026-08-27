from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from .config import Settings
from .fetcher import HttpFetcher
from .models import CrawlRunCreate
from .parser import discover_product_links
from .queueing import InMemoryQueue, OutboxPublisher
from .service import TargetProcessor
from .storage import Store


async def run_books_demo(product_limit: int) -> dict[str, int | float | str]:
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
        return {
            "run_id": str(run.id),
            "listing_pages": listing_pages,
            "discovered_product_urls": len(product_urls),
            "succeeded": summary.succeeded,
            "failed": summary.failed,
            "blocked": summary.blocked,
            "fetch_attempts": metrics["attempts"],
            "product_snapshots": metrics["products"],
            "success_rate": round(summary.succeeded / len(product_urls), 4),
        }
    finally:
        await fetcher.close()


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
