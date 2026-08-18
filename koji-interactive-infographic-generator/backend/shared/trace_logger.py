"""Structured, per-run telemetry with no external service dependency."""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from shared.token_budget import estimate_tokens

logger = logging.getLogger("eduvision.trace")


@dataclass
class TraceLogger:
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: float = field(default_factory=time.perf_counter)
    events: list[dict[str, Any]] = field(default_factory=list)
    token_usage: dict[str, int] = field(default_factory=dict)

    def event(self, name: str, **fields: Any) -> None:
        record = {
            "trace_id": self.trace_id,
            "event": name,
            "elapsed_ms": round((time.perf_counter() - self.started_at) * 1000, 2),
            **fields,
        }
        self.events.append(record)
        logger.info(json.dumps(record, default=str, sort_keys=True))

    def count_tokens(self, agent: str, text: str) -> int:
        count = estimate_tokens(text)
        self.token_usage[agent] = self.token_usage.get(agent, 0) + count
        return count

    @contextmanager
    def span(self, name: str, **fields: Any) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        except Exception as exc:
            self.event(name, status="error", duration_ms=round((time.perf_counter() - started) * 1000, 2), error=str(exc), **fields)
            raise
        else:
            self.event(name, status="ok", duration_ms=round((time.perf_counter() - started) * 1000, 2), **fields)

