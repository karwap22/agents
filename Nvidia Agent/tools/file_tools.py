from pathlib import Path


READABLE_EXTENSIONS = {".py", ".json", ".md", ".txt", ".toml", ".yaml", ".yml", ".csv"}
MAX_READ_BYTES = 100_000


def read_text_file(path, trace):
    project_root = Path(__file__).resolve().parent.parent
    trace("tool_read_requested", {"path": path})
    target = (project_root / path).resolve()
    try:
        target.relative_to(project_root)
    except ValueError:
        return "Rejected: path is outside the agent folder."
    if target.suffix.lower() not in READABLE_EXTENSIONS:
        return "Rejected: file type is not allowed."
    if not target.is_file():
        return "Rejected: file does not exist."
    if target.stat().st_size > MAX_READ_BYTES:
        return "Rejected: file is too large."
    trace("tool_read_completed", {"path": path, "bytes": target.stat().st_size})
    return target.read_text()
