from __future__ import annotations

import asyncio
import logging

from .config import get_settings
from .fetcher import HttpFetcher
from .queueing import OutboxPublisher, RedisStreamQueue
from .service import TargetProcessor
from .storage import Store


async def run_worker() -> None:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    store = Store(settings.database_url)
    store.init_schema()
    queue = RedisStreamQueue(settings.redis_url, settings.stream_name, settings.consumer_group)
    await queue.ensure()
    publisher = OutboxPublisher(store, queue)
    fetcher = HttpFetcher(
        allowed_hosts=settings.allowed_hosts,
        private_host_allowlist=settings.private_host_allowlist,
        allow_private_hosts=settings.allow_private_hosts,
        max_concurrency_per_host=settings.max_concurrency_per_host,
        min_host_interval_seconds=settings.min_host_interval_ms / 1000,
        max_response_bytes=settings.max_response_bytes,
    )
    processor = TargetProcessor(store, fetcher, settings)
    try:
        while True:
            await publisher.publish_due()
            messages = await queue.reclaim(settings.worker_name, count=20)
            if not messages:
                messages = await queue.read(settings.worker_name, count=20, block_ms=1000)
            if not messages:
                continue
            results = await asyncio.gather(*(processor.process(item.payload) for item in messages))
            for item, result in zip(messages, results, strict=True):
                await queue.ack(item.message_id)
                logging.info("target=%s result=%s", item.payload.target_id, result)
    finally:
        await fetcher.close()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
