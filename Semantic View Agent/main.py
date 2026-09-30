import json
import time

from llm import MODEL, call_model, get_client
from postgres import describe_table, list_schemas, list_tables, run_read_only_query
from tracing import trace


SEMANTIC_PROMPT = """You are a careful analytics engineer. Create reviewable semantic-view proposals from supplied PostgreSQL metadata. Do not invent business rules: list uncertain assumptions and questions. Return JSON only with a semantic_views array. Each view needs name, source_table, description, grain, primary_key, dimensions, measures, joins, assumptions, and questions."""

TOOLS = [
    {"type": "function", "function": {"name": "trace_action", "description": "Record a short public reason for the next action. Use before every database or semantic-generation tool; do not include private chain-of-thought.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "reason": {"type": "string"}}, "required": ["action", "reason"]}}},
    {"type": "function", "function": {"name": "list_schemas", "description": "List available PostgreSQL schemas.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "list_tables", "description": "List base tables in a PostgreSQL schema.", "parameters": {"type": "object", "properties": {"schema": {"type": "string"}}, "required": ["schema"]}}},
    {"type": "function", "function": {"name": "describe_table", "description": "Show columns, primary key, and foreign keys for one PostgreSQL table.", "parameters": {"type": "object", "properties": {"schema": {"type": "string"}, "table": {"type": "string"}}, "required": ["schema", "table"]}}},
    {"type": "function", "function": {"name": "run_read_only_query", "description": "Run one read-only SELECT or WITH query. Use for questions about data, counts, sums, trends, and grouped results. Results are limited to 200 rows and time out after 10 seconds.", "parameters": {"type": "object", "properties": {"sql": {"type": "string", "description": "A single PostgreSQL SELECT or WITH query."}}, "required": ["sql"]}}},
    {"type": "function", "function": {"name": "create_semantic_view", "description": "Create a semantic-view proposal for selected PostgreSQL tables.", "parameters": {"type": "object", "properties": {"schema": {"type": "string"}, "tables": {"type": "array", "items": {"type": "string"}}, "request": {"type": "string"}}, "required": ["schema", "tables", "request"]}}},
]


def trace_action(action, reason):
    trace("llm_decision", action=action, reason=reason)
    return {"recorded": True}


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


TOOL_MAP = {"trace_action": trace_action, "list_schemas": list_schemas, "list_tables": list_tables, "describe_table": describe_table, "run_read_only_query": run_read_only_query, "create_semantic_view": create_semantic_view}


def main():
    messages = [{"role": "system", "content": "You are a semantic-view assistant for PostgreSQL. Use tools to inspect the database before answering database questions. Use run_read_only_query for questions requiring actual row data or aggregates. Never claim a table, column, relationship, or query result exists unless a tool result confirms it. Before every database or semantic-generation tool call, call trace_action once with a concise public reason for the action. Do not reveal private chain-of-thought."}]
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
            started = time.perf_counter()
            response = get_client().chat.completions.create(model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto")
            message = response.choices[0].message
            trace("model_response_received", duration_ms=round((time.perf_counter() - started) * 1000), tool_calls=len(message.tool_calls or []))
            if not message.tool_calls:
                print(f"Agent: {message.content}\n")
                messages.append(message)
                trace("agent_response_completed", length=len(message.content or ""))
                break
            messages.append(message)
            for tool_call in message.tool_calls:
                try:
                    arguments = json.loads(tool_call.function.arguments)
                    trace("tool_requested", tool=tool_call.function.name, arguments=arguments)
                    started = time.perf_counter()
                    result = TOOL_MAP[tool_call.function.name](**arguments)
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                    result = {"error": str(error)}
                    trace("tool_failed", tool=tool_call.function.name, error=str(error))
                else:
                    trace("tool_completed", tool=tool_call.function.name, duration_ms=round((time.perf_counter() - started) * 1000))
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)})


if __name__ == "__main__":
    main()
