import re

from llm import call_model
from tracing import trace
from utils import parse_json


ALLOWED_ACTIONS = {"answer", "memory_lookup", "read_file"}


def validate_step(step):
    if not isinstance(step, dict) or step.get("action") not in ALLOWED_ACTIONS:
        return None
    if step["action"] == "read_file" and not isinstance(step.get("path"), str):
        return None
    return step


def create_plan(question):
    if re.search(r"\b(read|open|inspect)\b", question.lower()) and re.search(r"\b(summarize|summary|explain)\b", question.lower()):
        path_match = re.search(r"(?:read|open|inspect)\s+([^\s]+)", question, re.IGNORECASE)
        if path_match:
            plan = {"steps": [{"action": "read_file", "path": path_match.group(1)}, {"action": "answer"}]}
            trace("plan_created", {"actions": ["read_file", "answer"]})
            return plan
    response = call_model(
        [
            {"role": "system", "content": "Choose one action or up to three steps. Return JSON only. Allowed actions: answer, memory_lookup, read_file. Never choose writes, shell commands, or unknown actions."},
            {"role": "user", "content": question},
        ],
        temperature=0,
        max_tokens=100,
    )
    plan = parse_json(response)
    if isinstance(plan, dict) and isinstance(plan.get("steps"), list):
        steps = [validate_step(step) for step in plan["steps"][:3]]
        plan = {"steps": steps} if steps and all(steps) else {"action": "answer"}
    else:
        plan = validate_step(plan) or {"action": "answer"}
    trace("plan_created", {"actions": [step["action"] for step in plan.get("steps", [plan])]})
    return plan
