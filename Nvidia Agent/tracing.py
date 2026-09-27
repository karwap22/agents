import json
from datetime import datetime

from config import TRACE_ENABLED, TRACE_FILE


def trace(step, details=None):
    if not TRACE_ENABLED:
        return
    event = {"time": datetime.now().isoformat(timespec="seconds"), "step": step}
    if details:
        event.update(details)
    with open(TRACE_FILE, "a") as file:
        file.write(json.dumps(event) + "\n")
    print(f"[trace] {step}" + (f": {details}" if details else ""))
