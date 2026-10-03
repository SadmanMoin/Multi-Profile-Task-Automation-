"""Bounded retries. A step never retries forever."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    count: int = 2
    delay_ms: int = 3000

    @property
    def max_attempts(self) -> int:
        return max(0, self.count) + 1

    def should_retry(self, attempt: int) -> bool:
        """`attempt` is the attempt that just failed, starting at 1."""
        return attempt < self.max_attempts

    def delay_seconds(self) -> float:
        return max(0, self.delay_ms) / 1000


def policy_for(retry_count: int, retry_delay_ms: int) -> RetryPolicy:
    return RetryPolicy(count=max(0, int(retry_count)), delay_ms=max(0, int(retry_delay_ms)))
