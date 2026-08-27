from pathlib import Path

import httpx
import pytest

from catalog_forge.config import Settings
from catalog_forge.fetcher import HttpFetcher
from catalog_forge.fixture_app import app
from catalog_forge.models import CrawlRunCreate
from catalog_forge.queueing import InMemoryQueue, OutboxPublisher
from catalog_forge.service import TargetProcessor
from catalog_forge.storage import Store


def settings_for(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'pipeline.sqlite'}",
        allowed_hosts=["fixture"],
        allow_private_hosts=True,
        min_host_interval_ms=0,
        max_attempts=3,
    )


async def processor_for(tmp_path: Path):
    settings = settings_for(tmp_path)
    store = Store(settings.database_url)
    store.init_schema()
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture")
    fetcher = HttpFetcher(
        client=client,
        allowed_hosts=["fixture"],
        allow_private_hosts=True,
        min_host_interval_seconds=0,
        enforce_robots=True,
    )
    return settings, store, client, TargetProcessor(store, fetcher, settings)


@pytest.mark.asyncio
async def test_pipeline_processes_product_exactly_once(tmp_path: Path) -> None:
    settings, store, client, processor = await processor_for(tmp_path)
    run = store.create_run(
        CrawlRunCreate(connector="generic", start_urls=["http://fixture/products/1"], render_mode="http"),
        max_attempts=settings.max_attempts,
    )
    queue = InMemoryQueue()
    publisher = OutboxPublisher(store, queue)
    assert await publisher.publish_due() == 1
    message = (await queue.read("test"))[0]

    assert await processor.process(message.payload) == "succeeded"
    assert await processor.process(message.payload) == "already_terminal"
    assert len(store.list_products()) == 1
    assert store.get_run(run.id).succeeded == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_transient_failure_is_requeued_and_recovers(tmp_path: Path) -> None:
    settings, store, client, processor = await processor_for(tmp_path)
    store.create_run(
        CrawlRunCreate(connector="generic", start_urls=["http://fixture/unstable/991?failures=1"], render_mode="http"),
        max_attempts=settings.max_attempts,
    )
    queue = InMemoryQueue()
    publisher = OutboxPublisher(store, queue)
    await publisher.publish_due()
    first = (await queue.read("test"))[0]

    assert await processor.process(first.payload) == "retrying"
    assert await publisher.publish_due() == 1
    retry = (await queue.read("test"))[0]
    assert await processor.process(retry.payload) == "succeeded"
    assert len(store.list_products()) == 1
    attempts = store.list_fetch_attempts()
    assert [attempt["status_code"] for attempt in attempts] == [429, 200]
    assert [attempt["error_code"] for attempt in attempts] == ["http_429", None]
    await client.aclose()


@pytest.mark.asyncio
async def test_robots_disallow_is_blocked_without_retry(tmp_path: Path) -> None:
    settings, store, client, processor = await processor_for(tmp_path)
    store.create_run(
        CrawlRunCreate(connector="generic", start_urls=["http://fixture/blocked/product"], render_mode="http"),
        max_attempts=settings.max_attempts,
    )
    queue = InMemoryQueue()
    publisher = OutboxPublisher(store, queue)
    await publisher.publish_due()
    message = (await queue.read("test"))[0]

    assert await processor.process(message.payload) == "blocked"
    assert store.pending_outbox() == []
    await client.aclose()


@pytest.mark.asyncio
async def test_low_confidence_fingerprint_change_creates_drift_review(tmp_path: Path) -> None:
    settings, store, client, processor = await processor_for(tmp_path)
    store.create_run(
        CrawlRunCreate(
            connector="generic",
            start_urls=[
                "http://fixture/products/41",
                "http://fixture/products/42?variant=drift",
            ],
            render_mode="http",
        ),
        max_attempts=settings.max_attempts,
    )
    queue = InMemoryQueue()
    publisher = OutboxPublisher(store, queue)
    await publisher.publish_due()
    messages = await queue.read("test", count=10)

    assert [await processor.process(message.payload) for message in messages] == ["succeeded", "succeeded"]
    reviews = store.list_review_items()
    assert len(reviews) == 1
    assert reviews[0]["reason"] == "schema_drift"
    assert store.source_health()[0]["last_drift_at"] is not None
    await client.aclose()
