import json

from llm import MODEL, call_model, get_client
from postgres import describe_table, list_schemas, list_tables
from tracing import trace


SEMANTIC_PROMPT = """You are a careful analytics engineer. Create reviewable semantic-view proposals from supplied PostgreSQL metadata. Do not invent business rules: list uncertain assumptions and questions. Return JSON only with a semantic_views array. Each view needs name, source_table, description, grain, primary_key, dimensions, measures, joins, assumptions, and questions."""

TOOLS = [
    {"type": "function", "function": {"name": "list_schemas", "description": "List available PostgreSQL schemas.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "list_tables", "description": "List base tables in a PostgreSQL schema.", "parameters": {"type": "object", "properties": {"schema": {"type": "string"}}, "required": ["schema"]}}},
    {"type": "function", "function": {"name": "describe_table", "description": "Show columns, primary key, and foreign keys for one PostgreSQL table.", "parameters": {"type": "object", "properties": {"schema": {"type": "string"}, "table": {"type": "string"}}, "required": ["schema", "table"]}}},
    {"type": "function", "function": {"name": "create_semantic_view", "description": "Create a semantic-view proposal for selected PostgreSQL tables.", "parameters": {"type": "object", "properties": {"schema": {"type": "string"}, "tables": {"type": "array", "items": {"type": "string"}}, "request": {"type": "string"}}, "required": ["schema", "tables", "request"]}}},
]


def create_semantic_view(schema, tables, request):
    trace("semantic_generation_started", tables=len(tables), request_length=len(request))
    metadata = {"warehouse": "postgres", "schema": schema, "tables": [describe_table(schema, table) for table in tables]}
    content = call_model([
        {"role": "system", "content": SEMANTIC_PROMPT},
        {"role": "user", "content": f"Metadata: {json.dumps(metadata)}\nUser request: {request}"},
    ])
    proposal = json.loads(content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
    trace("semantic_generation_completed", views=len(proposal.get("semantic_views", [])))
    return proposal


TOOL_MAP = {"list_schemas": list_schemas, "list_tables": list_tables, "describe_table": describe_table, "create_semantic_view": create_semantic_view}


def main():
    messages = [{"role": "system", "content": "You are a semantic-view assistant for PostgreSQL. Use tools to inspect the database before answering database questions. Never claim a table, column, or relationship exists unless a tool result confirms it."}]
    print("Semantic View Agent (type exit to quit)")
    trace("agent_started")
    while True:
        prompt = input("You: ").strip()
        if prompt.lower() in {"exit", "quit"}:
            trace("agent_stopped")
            return
        if not prompt:
            continue
        messages.append({"role": "user", "content": prompt})
        trace("user_input_received", length=len(prompt))
        while True:
            trace("model_request_started", messages=len(messages))
            response = get_client().chat.completions.create(model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto")
            message = response.choices[0].message
            if not message.tool_calls:
                print(f"Agent: {message.content}\n")
                messages.append(message)
                trace("agent_response_completed", length=len(message.content or ""))
                break
            messages.append(message)
            for tool_call in message.tool_calls:
                trace("tool_requested", tool=tool_call.function.name)
                try:
                    result = TOOL_MAP[tool_call.function.name](**json.loads(tool_call.function.arguments))
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                    result = {"error": str(error)}
                    trace("tool_failed", tool=tool_call.function.name, error=str(error))
                else:
                    trace("tool_completed", tool=tool_call.function.name)
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)})


if __name__ == "__main__":
    main()
