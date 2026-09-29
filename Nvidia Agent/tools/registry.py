from tools.file_tools import read_text_file, search_text


TOOLS = {
    "read_file": {
        "description": "Read an approved text file inside the agent folder.",
        "mode": "read_only",
        "handler": read_text_file,
    },
    "search_text": {
        "description": "Search an approved text file inside the agent folder.",
        "mode": "read_only",
        "handler": search_text,
    },
}


def tool_catalog():
    return [
        {"name": name, "description": spec["description"], "mode": spec["mode"]}
        for name, spec in TOOLS.items()
    ]


def execute_tool(name, arguments, trace):
    spec = TOOLS.get(name)
    if spec is None:
        return {"ok": False, "tool": name, "result": None, "error": "unknown tool"}
    if spec["mode"] != "read_only":
        return {"ok": False, "tool": name, "result": None, "error": "tool is not allowed"}
    return spec["handler"](trace=trace, **arguments)
