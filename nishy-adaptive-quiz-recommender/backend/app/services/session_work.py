"""Small per-session executor for generation and enrichment work."""
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from typing import Callable


_executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="quiz-session")
_locks: dict[str, Lock] = {}
_locks_guard = Lock()


def _session_lock(session_id: str) -> Lock:
    with _locks_guard:
        return _locks.setdefault(session_id, Lock())


def _run_locked(session_id: str, fn: Callable, args: tuple) -> object:
    with _session_lock(session_id):
        return fn(*args)


def submit_session_work(session_id: str, fn: Callable, *args) -> Future:
    """Start work now while serializing mutations belonging to one session."""
    return _executor.submit(_run_locked, session_id, fn, args)
