import json
from datetime import datetime
from pathlib import Path


TRACE_FILE = Path(__file__).with_name("trace.jsonl")


def trace(step, **details):
    event = {"time": datetime.now().isoformat(timespec="seconds"), "step": step, **details}
    with TRACE_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event) + "\n")
    print(f"[trace] {step}")
