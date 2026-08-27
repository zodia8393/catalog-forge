from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import StrEnum


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(slots=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 30.0
    jitter_ratio: float = 0.2

    def delay_for(self, attempt: int, retry_after: float | None = None) -> float:
        if retry_after is not None:
            return min(max(retry_after, 0.0), self.max_delay_seconds)
        raw = min(self.base_delay_seconds * (2 ** max(attempt - 1, 0)), self.max_delay_seconds)
        jitter = raw * self.jitter_ratio
        return max(0.0, raw + random.uniform(-jitter, jitter))


@dataclass(slots=True)
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout_seconds: float = 20.0
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    opened_at: float | None = None

    def allow_request(self, now: float | None = None) -> bool:
        clock = now if now is not None else time.monotonic()
        if self.state == CircuitState.OPEN:
            if self.opened_at is not None and clock - self.opened_at >= self.recovery_timeout_seconds:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        return True

    def record_success(self) -> None:
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.opened_at = None

    def record_failure(self, now: float | None = None) -> None:
        self.consecutive_failures += 1
        if self.state == CircuitState.HALF_OPEN or self.consecutive_failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.opened_at = now if now is not None else time.monotonic()


@dataclass
class CircuitRegistry:
    failure_threshold: int = 5
    recovery_timeout_seconds: float = 20.0
    _breakers: dict[str, CircuitBreaker] = field(default_factory=dict)

    def for_host(self, host: str) -> CircuitBreaker:
        return self._breakers.setdefault(
            host,
            CircuitBreaker(self.failure_threshold, self.recovery_timeout_seconds),
        )
