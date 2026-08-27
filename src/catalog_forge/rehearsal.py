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

import httpx

from .config import Settings
from .fetcher import HttpFetcher
from .fixture_app import _attempts, app
from .models import CrawlRunCreate, CrawlRunSummary
from .queueing import InMemoryQueue, OutboxPublisher, QueuedMessage
from .service import TargetProcessor
from .storage import Store


@dataclass(slots=True)
class RehearsalExecution:
    report: dict[str, Any]
    run: CrawlRunSummary
    products: list[dict[str, Any]] = field(default_factory=list)
    attempts: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    html_samples: dict[str, dict[str, Any]] = field(default_factory=dict)


async def execute_rehearsal(target_count: int, *, capture: bool = False) -> RehearsalExecution:
    _attempts.clear()
    settings = Settings(
        database_url="sqlite:///:memory:",
        allowed_hosts=["fixture"],
        private_host_allowlist=["fixture"],
        min_host_interval_ms=0,
        max_concurrency_per_host=32,
        max_attempts=3,
    )
    store = Store(settings.database_url)
    store.init_schema()
    transient_ids = {index for index in range(1, target_count + 1) if index % 12 == 0}
    urls = [
        f"http://fixture/unstable/{index}?failures=1"
        if index in transient_ids
        else f"http://fixture/products/{index}"
        for index in range(1, target_count + 1)
    ]
    run = store.create_run(
        CrawlRunCreate(connector="fixture_chaos", start_urls=urls, max_pages=target_count, render_mode="http"),
        max_attempts=settings.max_attempts,
    )
    queue = InMemoryQueue()
    publisher = OutboxPublisher(store, queue)
    while await publisher.publish_due(limit=200):
        pass

    crashed = await queue.read("crashed-worker", count=min(17, target_count), block_ms=10)
    reclaimed = await queue.reclaim("recovery-worker", count=100)
    reclaim_ids = {item.message_id for item in reclaimed}
    if reclaim_ids != {item.message_id for item in crashed}:
        raise RuntimeError("reclaim contract mismatch")

    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture")
    fetcher = HttpFetcher(
        client=client,
        allowed_hosts=["fixture"],
        private_host_allowlist=["fixture"],
        max_concurrency_per_host=32,
        min_host_interval_seconds=0,
        enforce_robots=True,
    )
    processor = TargetProcessor(store, fetcher, settings)
    started = time.perf_counter()
    processed_ids: set[str] = set()
    captured_products: list[dict[str, Any]] = []
    captured_attempts: dict[str, list[dict[str, Any]]] = {}
    html_samples: dict[str, dict[str, Any]] = {}

    async def process_batch(messages: list[QueuedMessage]) -> None:
        results = await asyncio.gather(*(processor.process(item.payload) for item in messages))
        for item, result in zip(messages, results, strict=True):
            if result not in {"succeeded", "retrying", "already_terminal"}:
                raise RuntimeError(f"unexpected result: {result}")
            processed_ids.add(item.message_id)
            await queue.ack(item.message_id)

    try:
        await process_batch(reclaimed)
        while len(processed_ids) < target_count:
            batch = await queue.read("recovery-worker", count=64, block_ms=10)
            if not batch:
                break
            await process_batch(batch)

        while await publisher.publish_due(limit=200):
            pass
        recovered = 0
        while True:
            batch = await queue.read("recovery-worker", count=64, block_ms=10)
            if not batch:
                break
            results = await asyncio.gather(*(processor.process(item.payload) for item in batch))
            for item, result in zip(batch, results, strict=True):
                if result == "succeeded":
                    recovered += 1
                await queue.ack(item.message_id)

        elapsed = time.perf_counter() - started
        if capture:
            if not transient_ids:
                raise ValueError("capture requires at least one injected transient failure")
            normal_id = 42 if target_count >= 42 and 42 not in transient_ids else next(
                index for index in range(1, target_count + 1) if index not in transient_ids
            )
            recovered_id = 120 if 120 in transient_ids else min(transient_ids)
            product_rows = store.list_products(source="fixture_chaos", limit=target_count)
            by_external_id = {row["external_id"]: row for row in product_rows}
            selected = [
                ("normal", normal_id, by_external_id[f"SKU-{normal_id}"]),
                ("recovered", recovered_id, by_external_id[f"SKU-{recovered_id}"]),
            ]
            for label, product_id, product in selected:
                captured_products.append(product)
                captured_attempts[label] = store.list_fetch_attempts(
                    target_id=UUID(product["target_id"]),
                    limit=settings.max_attempts,
                )
                path = (
                    f"/unstable/{product_id}?failures=1"
                    if label == "recovered"
                    else f"/products/{product_id}"
                )
                response = await client.get(path)
                response.raise_for_status()
                html_samples[label] = {
                    "url": f"http://fixture{path}",
                    "status_code": response.status_code,
                    "html": response.text,
                    "bytes_received": len(response.content),
                }
    finally:
        await client.aclose()

    summary = store.get_run(run.id)
    metrics = store.metrics()
    if summary is None:
        raise RuntimeError("rehearsal run disappeared")
    report: dict[str, int | float | str] = {
        "run_id": str(run.id),
        "targets": target_count,
        "injected_transient_failures": len(transient_ids),
        "stale_messages_reclaimed": len(reclaimed),
        "transient_failures_recovered": recovered,
        "succeeded": summary.succeeded,
        "failed": summary.failed,
        "blocked": summary.blocked,
        "fetch_attempts": metrics["attempts"],
        "product_snapshots": metrics["products"],
        "lost_snapshots": max(target_count - metrics["products"], 0),
        "duplicate_snapshots": max(metrics["products"] - target_count, 0),
        "elapsed_seconds": round(elapsed, 3),
    }
    if (
        report["succeeded"] != target_count
        or report["lost_snapshots"] != 0
        or report["duplicate_snapshots"] != 0
    ):
        raise RuntimeError(f"rehearsal acceptance failed: {report}")
    return RehearsalExecution(
        report=report,
        run=summary,
        products=captured_products,
        attempts=captured_attempts,
        html_samples=html_samples,
    )


async def run_rehearsal(target_count: int) -> dict[str, Any]:
    return (await execute_rehearsal(target_count)).report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic failure-recovery rehearsal")
    parser.add_argument("--targets", type=int, default=1000)
    parser.add_argument("--output-root", type=Path, default=Path(os.environ.get("OUTPUT_ROOT", "artifacts")))
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    report = asyncio.run(run_rehearsal(args.targets))
    output = args.output_root / "recovery_rehearsal.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
