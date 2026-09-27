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
        return {"ok": False, "tool": "read_file", "result": None, "error": "path is outside the agent folder"}
    if target.suffix.lower() not in READABLE_EXTENSIONS:
        return {"ok": False, "tool": "read_file", "result": None, "error": "file type is not allowed"}
    if not target.is_file():
        return {"ok": False, "tool": "read_file", "result": None, "error": "file does not exist"}
    if target.stat().st_size > MAX_READ_BYTES:
        return {"ok": False, "tool": "read_file", "result": None, "error": "file is too large"}
    trace("tool_read_completed", {"path": path, "bytes": target.stat().st_size})
    return {"ok": True, "tool": "read_file", "result": target.read_text(), "error": None}

def search_text(path, query, trace):
    if not query or not query.strip():
        return {"ok": False, "tool": "search_text", "result": None, "error": "query is required"}
    project_root = Path(__file__).resolve().parent.parent
    trace("tool_search_text_requested", {"path": path})
    target = (project_root / path).resolve()
    try:
        target.relative_to(project_root)
    except ValueError:
        return {"ok": False, "tool": "search_text", "result": None, "error": "path is outside the agent folder"}
    if target.suffix.lower() not in READABLE_EXTENSIONS:
        return {"ok": False, "tool": "search_text", "result": None, "error": "file type is not allowed"}
    if not target.is_file():
        return {"ok": False, "tool": "search_text", "result": None, "error": "file does not exist"}
    if target.stat().st_size > MAX_READ_BYTES:
        return {"ok": False, "tool": "search_text", "result": None, "error": "file is too large"}
    query = query.strip().lower()
    matches = [
        f"Line {line_number}: {line}"
        for line_number, line in enumerate(target.read_text().splitlines(), start=1)
        if query in line.lower()
    ][:50]
    result = "\n".join(matches) if matches else "No matches found."
    trace("tool_search_text_completed", {"path": path, "match_count": len(matches)})
    return {"ok": True, "tool": "search_text", "result": result, "error": None}
