import json
from datetime import datetime
from pathlib import Path
from contextvars import ContextVar

TRACE_FILE = Path(__file__).resolve().parent / "Logs" / "trace.jsonl"
enabled = False

request_id_context = ContextVar("request_id", default=None)


def set_request_id(request_id):
    return request_id_context.set(request_id)


def reset_request_id(token):
    request_id_context.reset(token)


def set_enabled(value):
    global enabled
    enabled = value


def is_enabled():
    return enabled


def trace(step, **details):
    if not enabled:
        return

    event = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "step": step,
        **details,
    }

    request_id = request_id_context.get()
    if request_id:
        event["request_id"] = request_id

    with TRACE_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event) + "\n")

    print(f"[trace] {step}" + (f" {json.dumps(details)}" if details else ""))