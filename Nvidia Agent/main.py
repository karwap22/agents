import json
import re
from datetime import datetime
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from os import getenv
from tools.file_tools import read_text_file

load_dotenv()

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=getenv("API"),
)

TRACE_ENABLED = getenv("TRACE", "1") == "1"
MAX_RECENT_MESSAGES = 10
SYSTEM_MESSAGE = {"role": "system", "content": "You are a helpful assistant."}
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
MEMORY_FILE = DATA_DIR / "memory.json"
LESSONS_FILE = DATA_DIR / "lessons.json"
FACTS_FILE = DATA_DIR / "facts.json"
TRACE_FILE = DATA_DIR / "trace.jsonl"


def trace(step, details=None):
    if not TRACE_ENABLED:
        return
    event = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "step": step,
    }
    if details:
        event.update(details)
    with open(TRACE_FILE, "a") as file:
        file.write(json.dumps(event) + "\n")
    print(f"[trace] {step}" + (f": {details}" if details else ""))


def load_memory():
    try:
        with open(MEMORY_FILE) as file:
            return json.load(file)
    except FileNotFoundError:
        return [SYSTEM_MESSAGE]


def save_memory(messages):
    with open(MEMORY_FILE, "w") as file:
        json.dump(messages, file, indent=2)


def load_lessons():
    try:
        with open(LESSONS_FILE) as file:
            return json.load(file)
    except FileNotFoundError:
        return []


def save_lessons(lessons):
    with open(LESSONS_FILE, "w") as file:
        json.dump(lessons, file, indent=2)


def load_facts():
    try:
        with open(FACTS_FILE) as file:
            stored = json.load(file)
            return [
                fact if isinstance(fact, dict) else {"key": "legacy", "value": fact}
                for fact in stored
                if isinstance(fact, (dict, str))
            ]
    except FileNotFoundError:
        return []


def save_facts(facts):
    with open(FACTS_FILE, "w") as file:
        json.dump(facts, file, indent=2)


def parse_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None


# ponytail: full history grows forever; keep only recent messages when it reaches the model context limit.
lessons = load_lessons()
facts = load_facts()
save_facts(facts)


def build_system_content(selected_facts=None):
    selected_facts = facts if selected_facts is None else selected_facts
    content = "You are a helpful assistant."
    if selected_facts:
        content += (
            "\n\nKnown facts about the user (authoritative over conflicting "
            "conversation history):\n"
        )
        content += "\n".join(
            f"- {fact['key']}: {fact['value']}" for fact in selected_facts
        )
    if lessons:
        content += "\n\nUseful lessons from previous evaluations:\n"
        content += "\n".join(f"- {lesson}" for lesson in lessons)
    return content


def relevant_facts(question):
    stop_words = {"a", "an", "the", "is", "my", "what", "where", "who", "how"}
    question_words = set(re.findall(r"[a-z0-9]+", question.lower())) - stop_words
    selected = []
    for fact in facts:
        fact_words = set(re.findall(r"[a-z0-9]+", f"{fact['key']} {fact['value']}".lower()))
        if question_words & fact_words:
            selected.append(fact)
    return selected


def build_context(question, selected_facts):
    history = messages[1:-1][-MAX_RECENT_MESSAGES:]
    if selected_facts:
        fact_words = set(
            word
            for fact in selected_facts
            for word in re.findall(r"[a-z0-9]+", fact["key"].lower())
        )
        history = [
            message
            for message in history
            if not fact_words & set(re.findall(r"[a-z0-9]+", message["content"].lower()))
        ]
    return [messages[0]] + history + [messages[-1]]


messages = load_memory()
messages[0] = {
    "role": "system",
    "content": build_system_content(),
}


def review_answer(question, answer):
    completion = client.chat.completions.create(
        model="nvidia/nemotron-3-super-120b-a12b",
        messages=[
            {
                "role": "system",
                "content": (
                    "Review the answer for a reusable improvement. Reply with "
                    'valid JSON only: {"lesson": "one short actionable lesson"} '
                    'or {"lesson": null} if no lesson is needed.'
                ),
            },
            {"role": "user", "content": f"Question: {question}\nAnswer: {answer}"},
        ],
        temperature=0,
        max_tokens=100,
    )
    result = parse_json(completion.choices[0].message.content)
    lesson = result.get("lesson") if isinstance(result, dict) else None
    return lesson.strip() if isinstance(lesson, str) and lesson.strip() else None


def revise_answer(question, answer, lesson):
    completion = client.chat.completions.create(
        model="nvidia/nemotron-3-super-120b-a12b",
        messages=[
            {
                "role": "system",
                "content": "Improve the draft using the lesson. Return only the final answer.",
            },
            {
                "role": "user",
                "content": (
                    f"Question: {question}\nDraft answer: {answer}\n"
                    f"Lesson to apply: {lesson}"
                ),
            },
        ],
        temperature=0.3,
        max_tokens=1024,
    )
    revised = completion.choices[0].message.content.strip()
    return revised or answer


def extract_facts(question):
    completion = client.chat.completions.create(
        model="nvidia/nemotron-3-super-120b-a12b",
        messages=[
            {
                "role": "system",
                "content": (
                    "Extract only durable facts explicitly stated by the user. "
                    'Return valid JSON only: {"facts": [{"key": "...", "value": "..."}]} '
                    'or {"facts": []}. '
                    "Capture preferences and personal details stated by the user. "
                    "Use a stable snake_case key, such as favorite_place. "
                    "Do not infer facts from the assistant's answer."
                ),
            },
            {
                "role": "user",
                "content": f"User message: {question}",
            },
        ],
        temperature=0,
        max_tokens=150,
    )
    result = parse_json(completion.choices[0].message.content)
    new_facts = result.get("facts") if isinstance(result, dict) else []
    if not isinstance(new_facts, list):
        return []
    return [
        {"key": fact["key"].strip(), "value": fact["value"].strip()}
        for fact in new_facts
        if isinstance(fact, dict)
        and isinstance(fact.get("key"), str)
        and isinstance(fact.get("value"), str)
        and fact["key"].strip()
        and fact["value"].strip()
    ]


def show_memory():
    print("Facts:")
    for fact in facts:
        print(f"- {fact['key']}: {fact['value']}")
    print("Lessons:")
    for lesson in lessons:
        print(f"- {lesson}")


def forget_fact(query):
    if not query:
        print("Usage: /forget <text>")
        return
    query = query.lower()
    remaining = [
        fact for fact in facts
        if query not in fact["key"].lower() and query not in fact["value"].lower()
    ]
    removed = len(facts) - len(remaining)
    facts[:] = remaining
    save_facts(facts)
    messages[0]["content"] = build_system_content()
    print(f"Forgot {removed} fact(s).")


def clear_history():
    confirmation = input("Type CLEAR to remove conversation history: ")
    if confirmation != "CLEAR":
        print("History was not cleared.")
        return
    messages[:] = [{"role": "system", "content": build_system_content()}]
    save_memory(messages)
    trace("conversation_cleared")
    print("Conversation history cleared. Facts and lessons were preserved.")


def ask_agent(question):
    trace("input_received", {"length": len(question)})
    messages.append({"role": "user", "content": question})
    selected_facts = relevant_facts(question)
    trace("facts_selected", {"keys": [fact["key"] for fact in selected_facts]})
    messages[0]["content"] = build_system_content(selected_facts)
    context = build_context(question, selected_facts)
    trace("context_built", {"message_count": len(context)})
    completion = client.chat.completions.create(
        model="nvidia/nemotron-3-super-120b-a12b",
        messages=context,
        temperature=0.5,
        max_tokens=1024,
    )
    answer = completion.choices[0].message.content
    trace("draft_completed", {"length": len(answer)})
    lesson = review_answer(question, answer)
    trace("review_completed", {"lesson_found": lesson is not None})
    if lesson is not None:
        if lesson not in lessons:
            lessons.append(lesson)
        save_lessons(lessons)
        print(f"Lesson saved: {lesson}")
        answer = revise_answer(question, answer, lesson)
        trace("revision_completed", {"performed": True, "length": len(answer)})
    else:
        trace("revision_completed", {"performed": False})
    added_facts = []
    for fact in extract_facts(question):
        existing = next((item for item in facts if item["key"] == fact["key"]), None)
        if existing is None:
            facts.append(fact)
            added_facts.append(fact["key"])
            print(f"Fact saved: {fact['key']} = {fact['value']}")
        elif existing["value"] != fact["value"]:
            print(f"Fact updated: {fact['key']} = {fact['value']}")
            existing["value"] = fact["value"]
            added_facts.append(fact["key"])
    trace("fact_extraction_completed", {"keys": added_facts})
    if facts:
        save_facts(facts)
        messages[0]["content"] = build_system_content()
    messages.append({"role": "assistant", "content": answer})
    save_memory(messages)
    trace("memory_saved")
    return answer


while True:
    question = input("You: ")
    if question.lower() in {"quit", "exit"}:
        save_memory(messages)
        break
    if question == "/memory":
        show_memory()
        continue
    if question == "/clear-history":
        clear_history()
        continue
    if question.startswith("/read"):
        path = question[len("/read") :].strip()
        print(read_text_file(path, trace) if path else "Usage: /read <relative text-file path>")
        continue
    if question.startswith("/forget"):
        forget_fact(question[len("/forget") :].strip())
        continue
    print(f"Agent: {ask_agent(question)}")
