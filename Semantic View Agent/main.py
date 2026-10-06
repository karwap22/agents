import json
import time

from llm import call_model, chat_completion
from postgres import describe_table, list_schemas, list_tables, run_read_only_query
from tracing import is_enabled, set_enabled, trace
from tools import TOOLS
from prompts import SEMANTIC_PROMPT,AGENT_PROMPT,TRACE_PROMPT



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
    messages = [{"role": "system", "content": AGENT_PROMPT}]
    print("Semantic View Agent (type exit to quit; /trace on for debugging)")
    trace("agent_started")
    while True:
        prompt = input("You: ").strip()
        if prompt.lower() in {"exit", "quit","/exit", "/quit"}:
            trace("agent_stopped")
            return
        if prompt == "/trace on":
            set_enabled(True)
            messages[0]["content"] = AGENT_PROMPT + TRACE_PROMPT
            print("Tracing enabled.\n")
            trace("tracing_enabled")
            continue
        if prompt == "/trace off":
            trace("tracing_disabled")
            set_enabled(False)
            messages[0]["content"] = AGENT_PROMPT
            print("Tracing disabled.\n")
            continue
        if prompt == "/trace status":
            print(f"Tracing is {'on' if is_enabled() else 'off'}.\n")
            continue
        if not prompt:
            continue
        messages.append({"role": "user", "content": prompt})
        trace("user_input_received", length=len(prompt))
        while True:
            trace("model_request_started", messages=len(messages))
            started = time.perf_counter()
            tools = TOOLS if is_enabled() else [tool for tool in TOOLS if tool["function"]["name"] != "trace_action"]
            response = chat_completion(messages, tools=tools, tool_choice="auto")
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
