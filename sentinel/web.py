"""Nimble access with the boring production patterns: bounded concurrency,
Retry-After-aware backoff, and a content-addressed cache that doubles as a
replay log for offline demos."""

import hashlib
import json
import os
import random
import threading
import time

import nimble_python
from opik import opik_context, track

from .config import CACHE_DIR, REPLAY, nimble_client

# Nimble Search allows 10 QPS per account; stay under it with headroom.
_slots = threading.BoundedSemaphore(int(os.getenv("SENTINEL_MAX_CONCURRENCY", "6")))
MAX_ATTEMPTS = 4


class ReplayMiss(RuntimeError):
    pass


def _cache_path(kind: str, params: dict):
    digest = hashlib.sha256(json.dumps([kind, params], sort_keys=True).encode()).hexdigest()[:24]
    return CACHE_DIR / f"{kind}-{digest}.json"


def _cached_call(kind: str, params: dict, fn):
    path = _cache_path(kind, params)
    if path.exists():
        opik_context.update_current_span(metadata={"cache": "hit"})
        return json.loads(path.read_text())
    if REPLAY:
        raise ReplayMiss(f"{kind} not in replay cache: {params}")

    attempts = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with _slots:
                result = fn()
            break
        except nimble_python.RateLimitError as e:
            wait = float(e.response.headers.get("retry-after") or 2**attempt)
            attempts.append({"attempt": attempt, "error": "429", "wait_s": wait})
        except (nimble_python.APIConnectionError, nimble_python.APITimeoutError) as e:
            wait = 2**attempt + random.random()
            attempts.append({"attempt": attempt, "error": type(e).__name__, "wait_s": wait})
        except nimble_python.APIStatusError as e:
            # 5xx and Nimble's 555 timeout are retryable; other 4xx are not.
            if e.status_code < 500:
                raise
            wait = 2**attempt + random.random()
            attempts.append({"attempt": attempt, "error": str(e.status_code), "wait_s": wait})
        if attempt == MAX_ATTEMPTS:
            opik_context.update_current_span(metadata={"cache": "miss", "retries": attempts})
            raise RuntimeError(f"{kind} failed after {MAX_ATTEMPTS} attempts: {attempts}")
        time.sleep(wait)

    CACHE_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(result))
    opik_context.update_current_span(metadata={"cache": "miss", "retries": attempts})
    return result


@track(name="nimble.search", type="tool")
def search(query: str, **options) -> list[dict]:
    """Live web search. Defaults to lite depth because it is the fast path."""
    params = {"query": query, "search_depth": "lite", "max_results": 6, **options}

    def call():
        resp = nimble_client().search(**params)
        return [
            {"title": r.title, "url": r.url, "description": r.description, "content": r.content}
            for r in resp.results
        ]

    return _cached_call("search", params, call)


@track(name="nimble.extract", type="tool")
def extract(url: str) -> dict:
    """Fetch one page. We keep the raw HTML because hidden-text checks need it;
    markdown converters silently drop the CSS that hides injected text."""
    params = {"url": url, "render": "auto", "formats": ["markdown", "html"]}

    def call():
        resp = nimble_client().extract.run(**params)
        return {
            "url": url,
            "status": resp.status,
            "markdown": resp.data.markdown or "",
            "html": resp.data.html or "",
        }

    return _cached_call("extract", params, call)
