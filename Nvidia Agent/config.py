import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

MEMORY_FILE = DATA_DIR / "memory.json"
LESSONS_FILE = DATA_DIR / "lessons.json"
FACTS_FILE = DATA_DIR / "facts.json"
TRACE_FILE = DATA_DIR / "trace.jsonl"
TRACE_ENABLED = os.getenv("TRACE", "1") == "1"
MAX_RECENT_MESSAGES = 10
