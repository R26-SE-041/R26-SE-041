"""Bounded transient caches; failed requests are never cached, concurrent work is shared."""
import asyncio
import time
from collections import OrderedDict


class AsyncCache:
    def __init__(self, *, ttl=600, max_bytes=32 * 1024 * 1024, max_entries=128):
        self.ttl, self.max_bytes, self.max_entries = ttl, max_bytes, max_entries
        self.entries = OrderedDict()
        self.pending = {}
        self.size = 0

    async def get(self, key, create, *, size=len):
        now = time.monotonic()
        for old_key, (_, expiry, weight) in list(self.entries.items()):
            if expiry <= now:
                self.entries.pop(old_key)
                self.size -= weight
        if key in self.entries:
            self.entries.move_to_end(key)
            return self.entries[key][0]
        if key not in self.pending:
            async def generate():
                try:
                    value = await create()
                    weight = size(value)
                    if 0 < weight <= self.max_bytes:
                        while self.entries and (self.size + weight > self.max_bytes or len(self.entries) >= self.max_entries):
                            _, (_, _, removed) = self.entries.popitem(last=False)
                            self.size -= removed
                        self.entries[key] = (value, time.monotonic() + self.ttl, weight)
                        self.size += weight
                    return value
                finally:
                    self.pending.pop(key, None)
            task = asyncio.create_task(generate())
            # Observe failures even if the last browser disconnects.
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
            self.pending[key] = task
        return await asyncio.shield(self.pending[key])


speech = AsyncCache()
embeddings = AsyncCache(max_bytes=1024 * 1024)
documents = AsyncCache(max_bytes=16 * 1024 * 1024, max_entries=32)
