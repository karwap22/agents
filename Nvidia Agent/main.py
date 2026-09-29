import json

from agent import Agent
from memory import Memory
from planner import create_plan
from tools.registry import execute_tool
from tracing import trace


memory = Memory()
agent = Agent(memory)


def show_memory():
    print("Facts:")
    for fact in memory.facts:
        print(f"- {fact['key']}: {fact['value']} (updated {fact['updated_at']})")
    print("Lessons:")
    for lesson in memory.lessons:
        print(f"- {lesson}")


def show_candidates():
    print("Candidate lessons:")
    for candidate in memory.candidates:
        print(f"- {candidate}")
    if not memory.candidates:
        print("(none)")


def forget_fact(query):
    if not query:
        print("Usage: /forget <text>")
        return
    query = query.lower()
    remaining = [
        fact for fact in memory.facts
        if query not in fact["key"].lower() and query not in fact["value"].lower()
    ]
    removed = len(memory.facts) - len(remaining)
    memory.facts[:] = remaining
    memory.save_facts()
    memory.messages[0]["content"] = memory.build_system_content()
    print(f"Forgot {removed} fact(s).")


def remember_fact(spec):
    if "=" not in spec:
        print("Usage: /remember key=value")
        return
    key, value = (part.strip() for part in spec.split("=", 1))
    if not key or not value:
        print("Usage: /remember key=value")
        return
    status = memory.add_or_update_fact({"key": key, "value": value}, "explicit_command")
    memory.save_facts()
    memory.messages[0]["content"] = memory.build_system_content()
    print(f"Fact {status}: {key}")


def clear_history():
    confirmation = input("Type CLEAR to remove conversation history: ")
    if confirmation != "CLEAR":
        print("History was not cleared.")
        return
    memory.messages[:] = [{"role": "system", "content": memory.build_system_content()}]
    memory.save_messages()
    trace("conversation_cleared")
    print("Conversation history cleared. Facts and lessons were preserved.")


def save_local_answer(question, answer):
    memory.messages.append({"role": "user", "content": question})
    memory.messages.append({"role": "assistant", "content": answer})
    memory.save_messages()
    trace("memory_saved")


def execute_plan(question, plan):
    steps = plan.get("steps", [plan])
    trace("plan_execution_started", {"steps": len(steps)})
    tool_result = None
    for index, step in enumerate(steps, start=1):
        action = step["action"]
        trace("plan_step_started", {"index": index, "action": action})
        if action == "answer":
            prompt = question
            if tool_result is not None:
                if not tool_result["ok"]:
                    answer = f"Tool failed: {tool_result['error']}"
                    save_local_answer(question, answer)
                    trace("plan_execution_failed", {"index": index, "error": tool_result["error"]})
                    return answer
                prompt += f"\n\nTool result from {tool_result['tool']}:\n{tool_result['result']}"
            answer = agent.ask(prompt)
            trace("plan_step_completed", {"index": index, "action": action})
            return answer
        if action == "memory_lookup":
            broad = any(word in question.lower() for word in ("what do you remember", "saved memories", "lessons"))
            selected = memory.facts if broad else memory.select_relevant_facts(question)
            lines = [f"- {fact['key']}: {fact['value']}" for fact in selected]
            if broad:
                lines.extend(f"- lesson: {lesson}" for lesson in memory.lessons)
            tool_result = {
                "ok": True,
                "tool": "memory_lookup",
                "result": "\n".join(lines) if lines else "I do not have any matching memories.",
                "error": None,
            }
        else:
            arguments = {key: value for key, value in step.items() if key != "action"}
            tool_result = execute_tool(action, arguments, trace)
        trace("plan_step_completed", {"index": index, "action": action})
    answer = (
        tool_result["result"] if tool_result and tool_result["ok"]
        else f"Tool failed: {tool_result['error']}" if tool_result
        else "The plan produced no result."
    )
    save_local_answer(question, answer)
    trace("plan_execution_completed", {"steps": len(steps)})
    return answer


while True:
    question = input("You: ")
    if question.lower() in {"quit", "exit"}:
        memory.save_messages()
        break
    if question == "/memory":
        show_memory()
        continue
    if question == "/candidates":
        show_candidates()
        continue
    if question == "/clear-history":
        clear_history()
        continue
    if question.startswith("/plan"):
        request = question[len("/plan") :].strip()
        print(json.dumps(create_plan(request), indent=2) if request else "Usage: /plan <request>")
        continue
    if question.startswith("/read"):
        path = question[len("/read") :].strip()
        if not path:
            print("Usage: /read <relative text-file path>")
        else:
            result = execute_tool("read_file", {"path": path}, trace)
            print(result["result"] if result["ok"] else f"Rejected: {result['error']}")
        continue
    if question == "/search" or question.startswith("/search "):
        parts = question.split(maxsplit=2)
        if len(parts) < 3:
            print("Usage: /search <relative text-file path> <query>")
        else:
            result = execute_tool("search_text", {"path": parts[1], "query": parts[2]}, trace)
            print(result["result"] if result["ok"] else f"Rejected: {result['error']}")
        continue

    if question.startswith("/forget"):
        forget_fact(question[len("/forget") :].strip())
        continue
    if question.startswith("/remember"):
        remember_fact(question[len("/remember") :].strip())
        continue
    plan = create_plan(question)
    print(f"Agent: {execute_plan(question, plan)}")
