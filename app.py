"""Web front end (and the Vercel entrypoint). Streams Sentinel's live events
as NDJSON so the page can show each fetch, flag and verdict as it happens.

    uv run uvicorn app:app --reload
"""

import json
import queue
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

import opik
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

import sentinel  # noqa: F401  (loads .env and tracing config first)
from sentinel.agent import scan_url

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="Sentinel", docs_url=None, redoc_url=None)

# Public demo with real API keys behind it: a small per-IP budget per instance.
RATE_LIMIT, RATE_WINDOW_S = 6, 600
_hits: dict[str, deque] = defaultdict(deque)
_hits_lock = threading.Lock()


def _allowed(ip: str) -> bool:
    now = time.time()
    with _hits_lock:
        q = _hits[ip]
        while q and now - q[0] > RATE_WINDOW_S:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            return False
        q.append(now)
        return True


@app.get("/", response_class=HTMLResponse)
def index():
    return (ROOT / "web" / "index.html").read_text()


@app.get("/quillstack", response_class=HTMLResponse)
def quillstack():
    """The trap page, so anyone can see it looks normal to a human."""
    return (ROOT / "docs" / "quillstack" / "index.html").read_text()


@app.get("/api/radar")
def radar():
    return json.loads((ROOT / "data" / "radar_snapshot.json").read_text())


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/scan")
async def scan(request: Request):
    body = await request.json()
    url = str(body.get("url", "")).strip()
    if url != "fixture:quillstack" and not (url.startswith(("http://", "https://")) and len(url) < 2000):
        return JSONResponse({"error": "Enter a full http(s) URL"}, status_code=400)
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0].strip()
    if not _allowed(ip):
        return JSONResponse({"error": "Rate limit: 6 scans per 10 minutes. Try again shortly."}, status_code=429)

    events: queue.Queue = queue.Queue()
    t0 = time.perf_counter()

    def emit(kind: str, **data):
        events.put({"type": kind, "t": round(time.perf_counter() - t0, 1), **data})

    def work():
        try:
            result = scan_url(url, emit=emit, compare=True)
            result.pop("clean_text", None)
            events.put({"type": "result", "data": result})
        except Exception as e:  # surface failures in the console instead of a dead stream
            events.put({"type": "error", "t": round(time.perf_counter() - t0, 1), "msg": f"{type(e).__name__}: {e}"})
        finally:
            events.put(None)
            opik.flush_tracker()

    threading.Thread(target=work, daemon=True).start()

    def stream():
        while True:
            try:
                item = events.get(timeout=10)
            except queue.Empty:
                yield json.dumps({"type": "ping"}) + "\n"  # keeps proxies from closing an idle stream
                continue
            if item is None:
                return
            yield json.dumps(item, default=str) + "\n"

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
