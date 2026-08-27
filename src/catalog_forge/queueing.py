from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Protocol

from .models import TargetMessage


@dataclass(slots=True)
class QueuedMessage:
    message_id: str
    payload: TargetMessage


class MessageQueue(Protocol):
    async def ensure(self) -> None: ...
    async def enqueue(self, message: TargetMessage) -> str: ...
    async def read(self, consumer: str, *, count: int = 10, block_ms: int = 1000) -> list[QueuedMessage]: ...
    async def ack(self, message_id: str) -> None: ...
    async def reclaim(self, consumer: str, *, idle_ms: int = 30_000, count: int = 100) -> list[QueuedMessage]: ...


class InMemoryQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[QueuedMessage] = asyncio.Queue()
        self._pending: dict[str, QueuedMessage] = {}
        self._sequence = 0

    async def ensure(self) -> None:
        return None

    async def enqueue(self, message: TargetMessage) -> str:
        self._sequence += 1
        message_id = str(self._sequence)
        await self._queue.put(QueuedMessage(message_id, message))
        return message_id

    async def read(self, consumer: str, *, count: int = 10, block_ms: int = 1000) -> list[QueuedMessage]:
        del consumer
        messages: list[QueuedMessage] = []
        try:
            first = await asyncio.wait_for(self._queue.get(), timeout=block_ms / 1000)
        except TimeoutError:
            return []
        messages.append(first)
        self._pending[first.message_id] = first
        while len(messages) < count and not self._queue.empty():
            item = self._queue.get_nowait()
            self._pending[item.message_id] = item
            messages.append(item)
        return messages

    async def ack(self, message_id: str) -> None:
        self._pending.pop(message_id, None)

    async def reclaim(self, consumer: str, *, idle_ms: int = 30_000, count: int = 100) -> list[QueuedMessage]:
        del consumer, idle_ms
        return list(self._pending.values())[:count]


class RedisStreamQueue:
    def __init__(self, redis_url: str, stream: str, group: str):
        try:
            from redis.asyncio import from_url
        except ImportError as exc:
            raise RuntimeError("redis dependency is required for RedisStreamQueue") from exc
        self.redis = from_url(redis_url, decode_responses=True)
        self.stream = stream
        self.group = group

    async def ensure(self) -> None:
        try:
            await self.redis.xgroup_create(self.stream, self.group, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def enqueue(self, message: TargetMessage) -> str:
        return await self.redis.xadd(self.stream, {"payload": message.model_dump_json()})

    async def read(self, consumer: str, *, count: int = 10, block_ms: int = 1000) -> list[QueuedMessage]:
        rows = await self.redis.xreadgroup(
            self.group,
            consumer,
            {self.stream: ">"},
            count=count,
            block=block_ms,
        )
        return self._decode(rows)

    async def ack(self, message_id: str) -> None:
        await self.redis.xack(self.stream, self.group, message_id)

    async def reclaim(self, consumer: str, *, idle_ms: int = 30_000, count: int = 100) -> list[QueuedMessage]:
        _next, rows, _deleted = await self.redis.xautoclaim(
            self.stream,
            self.group,
            consumer,
            min_idle_time=idle_ms,
            start_id="0-0",
            count=count,
        )
        return [QueuedMessage(message_id, TargetMessage.model_validate_json(fields["payload"])) for message_id, fields in rows]

    @staticmethod
    def _decode(rows: list[object]) -> list[QueuedMessage]:
        decoded: list[QueuedMessage] = []
        for _stream, messages in rows:
            for message_id, fields in messages:
                decoded.append(QueuedMessage(message_id, TargetMessage.model_validate_json(fields["payload"])))
        return decoded


class OutboxPublisher:
    def __init__(self, store: object, queue: MessageQueue):
        self.store = store
        self.queue = queue

    async def publish_due(self, limit: int = 100) -> int:
        published = 0
        for row in self.store.pending_outbox(limit):
            await self.queue.enqueue(TargetMessage.model_validate(row["payload"]))
            self.store.mark_outbox_published(row["id"])
            published += 1
        return published
