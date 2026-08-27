from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
from pathlib import Path

import httpx

from .fetcher import HttpFetcher
from .fixture_app import app


async def run_case(page_count: int, concurrency: int, delay_ms: int) -> dict[str, float | int]:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://fixture")
    fetcher = HttpFetcher(
        client=client,
        allowed_hosts=["fixture"],
        allow_private_hosts=True,
        max_concurrency_per_host=concurrency,
        min_host_interval_seconds=0,
        enforce_robots=False,
    )
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []

    async def fetch_one(index: int) -> None:
        async with semaphore:
            result = await fetcher.fetch(f"http://fixture/products/{index}?delay_ms={delay_ms}")
            latencies.append(result.latency_ms)

    started = time.perf_counter()
    await asyncio.gather(*(fetch_one(index) for index in range(1, page_count + 1)))
    elapsed = time.perf_counter() - started
    await client.aclose()
    ordered = sorted(latencies)
    return {
        "pages": page_count,
        "concurrency": concurrency,
        "fixture_delay_ms": delay_ms,
        "elapsed_seconds": round(elapsed, 4),
        "throughput_pages_per_second": round(page_count / elapsed, 2),
        "p50_latency_ms": round(statistics.median(ordered), 3),
        "p95_latency_ms": round(ordered[max(int(len(ordered) * 0.95) - 1, 0)], 3),
        "failures": 0,
    }


async def benchmark(page_count: int, delay_ms: int = 10) -> dict[str, object]:
    baseline = await run_case(page_count, 1, delay_ms)
    concurrent = await run_case(page_count, 32, delay_ms)
    speedup = float(concurrent["throughput_pages_per_second"]) / max(float(baseline["throughput_pages_per_second"]), 0.001)
    return {"baseline": baseline, "concurrent": concurrent, "throughput_speedup": round(speedup, 2)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic CatalogForge concurrency benchmark")
    parser.add_argument("--pages", type=int, default=1000)
    parser.add_argument("--delay-ms", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = asyncio.run(benchmark(args.pages, args.delay_ms))
    output = args.output or Path(os.environ.get("OUTPUT_ROOT", "artifacts")) / "benchmark.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
