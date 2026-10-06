import json
from datetime import datetime
from pathlib import Path


TRACE_FILE = Path(__file__).resolve().parent / "Logs" / "trace.jsonl"
enabled = False


def set_enabled(value):
    global enabled
    enabled = value


def is_enabled():
    return enabled


def trace(step, **details):
    if not enabled:
        return
    event = {"time": datetime.now().isoformat(timespec="seconds"), "step": step, **details}
    with TRACE_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event) + "\n")
    print(f"[trace] {step}" + (f" {json.dumps(details)}" if details else ""))
