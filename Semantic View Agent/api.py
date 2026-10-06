import json
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request, HTTPException
from threading import BoundedSemaphore
from pydantic import BaseModel, Field

from main import run_agent_turn
from prompts import AGENT_PROMPT
from tracing import reset_request_id, set_request_id


app = FastAPI(title="Database Agent")

logger = logging.getLogger("database_agent")
logging.basicConfig(level=logging.INFO, format="%(message)s")

MAX_CONCURRENT_CHAT_REQUESTS = 10
chat_slots = BoundedSemaphore(MAX_CONCURRENT_CHAT_REQUESTS)


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    answer: str


@app.middleware("http")
async def observe_request(request: Request, call_next):
    request_id = uuid4().hex
    token = set_request_id(request_id)
    started = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - started) * 1000)

        logger.exception(json.dumps({
            "event": "http_request_failed",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "duration_ms": duration_ms,
        }))
        raise
    finally:
        reset_request_id(token)
    duration_ms = round((time.perf_counter() - started) * 1000)

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = str(duration_ms)

    logger.info(json.dumps({
        "event": "http_request_completed",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": duration_ms,
    }))

    return response

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not chat_slots.acquire(blocking=False):
        raise HTTPException(
            status_code=503,
            detail="Agent is busy. Try again shortly.",
            headers={"Retry-After": "1"},
        )

    try:
        messages = [{"role": "system", "content": AGENT_PROMPT}]
        answer, _ = run_agent_turn(messages, request.prompt)
        return ChatResponse(answer=answer)
    finally:
        chat_slots.release()