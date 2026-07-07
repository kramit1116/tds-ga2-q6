import time
import uuid
from collections import deque
from threading import Lock

from fastapi import FastAPI, Request, Query

EMAIL = "24f1000489@ds.study.iitm.ac.in" 

app = FastAPI()

START_TIME = time.time()

# --- Prometheus counter (manual, no extra dependency needed) ---
_counter_lock = Lock()
request_count = 0

# --- In-memory structured log buffer ---
_log_lock = Lock()
LOG_BUFFER = deque(maxlen=1000)


def log_event(level: str, path: str, request_id: str, **extra):
    entry = {
        "level": level,
        "ts": time.time(),
        "path": path,
        "request_id": request_id,
        **extra,
    }
    with _log_lock:
        LOG_BUFFER.append(entry)


@app.middleware("http")
async def instrument(request: Request, call_next):
    global request_count
    request_id = str(uuid.uuid4())

    with _counter_lock:
        request_count += 1

    response = await call_next(request)

    log_event(
        level="info",
        path=request.url.path,
        request_id=request_id,
        method=request.method,
        status_code=response.status_code,
    )

    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/work")
async def work(n: int = Query(1, ge=0)):
    # simulate K units of work
    total = 0
    for i in range(n):
        total += i
    return {"email": EMAIL, "done": n}


@app.get("/metrics")
async def metrics():
    with _counter_lock:
        count = request_count
    body = (
        "# HELP http_requests_total Total number of HTTP requests.\n"
        "# TYPE http_requests_total counter\n"
        f"http_requests_total {count}\n"
    )
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content=body, media_type="text/plain; version=0.0.4")


@app.get("/healthz")
async def healthz():
    uptime = time.time() - START_TIME
    return {"status": "ok", "uptime_s": uptime}


@app.get("/logs/tail")
async def logs_tail(limit: int = Query(10, ge=1, le=1000)):
    with _log_lock:
        entries = list(LOG_BUFFER)[-limit:]
    return entries
