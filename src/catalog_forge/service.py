from __future__ import annotations

import time

from .config import Settings
from .fetcher import FetchError, HttpFetcher
from .models import FetchAttemptRecord, RenderMode, TargetMessage
from .parser import parse_product
from .reliability import RetryPolicy
from .storage import Store


class TargetProcessor:
    def __init__(self, store: Store, fetcher: HttpFetcher, settings: Settings):
        self.store = store
        self.fetcher = fetcher
        self.settings = settings
        self.retry_policy = RetryPolicy(max_attempts=settings.max_attempts)

    async def process(self, message: TargetMessage) -> str:
        attempt = self.store.mark_started(message.target_id)
        if attempt is None:
            return "already_terminal"
        started = time.perf_counter()
        status_code: int | None = None
        received = 0
        try:
            result = await self.fetcher.fetch(message.url)
            status_code = result.status_code
            received = result.bytes_received
            html = result.text
            outcome = parse_product(
                html=html,
                url=result.final_url,
                run_id=message.run_id,
                target_id=message.target_id,
                source=message.connector,
            )
            if message.render_mode == RenderMode.BROWSER or (
                message.render_mode == RenderMode.AUTO and outcome.required_field_coverage < 0.5
            ):
                html = await self.fetcher.render(message.url)
                outcome = parse_product(
                    html=html,
                    url=message.url,
                    run_id=message.run_id,
                    target_id=message.target_id,
                    source=message.connector,
                )
            if outcome.product is None:
                raise FetchError("parse_failed", ",".join(outcome.warnings) or "product not found", transient=False)
            latency_ms = (time.perf_counter() - started) * 1000
            self.store.record_attempt(
                FetchAttemptRecord(
                    target_id=message.target_id,
                    attempt=attempt,
                    status_code=status_code,
                    latency_ms=latency_ms,
                    bytes_received=received,
                )
            )
            self.store.complete_target(
                outcome.product,
                coverage=outcome.required_field_coverage,
                confidence_threshold=self.settings.low_confidence_threshold,
            )
            return "succeeded"
        except FetchError as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            self.store.record_attempt(
                FetchAttemptRecord(
                    target_id=message.target_id,
                    attempt=attempt,
                    status_code=status_code,
                    latency_ms=latency_ms,
                    bytes_received=received,
                    error_code=exc.code,
                    retry_after_seconds=exc.retry_after,
                )
            )
            delay = self.retry_policy.delay_for(attempt, exc.retry_after)
            return self.store.fail_target(
                message.target_id,
                error_code=exc.code,
                transient=exc.transient,
                retry_delay_seconds=delay,
            ).value
