import json
from openai import OpenAI
from dotenv import load_dotenv
from os import getenv

load_dotenv()

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=getenv("API"),
)

MEMORY_FILE = "memory.json"
LESSONS_FILE = "lessons.json"
MAX_RECENT_MESSAGES = 10
SYSTEM_MESSAGE = {"role": "system", "content": "You are a helpful assistant."}


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


# ponytail: full history grows forever; keep only recent messages when it reaches the model context limit.
lessons = load_lessons()

system_content = "You are a helpful assistant."

if lessons:
    system_content += "\n\nUseful lessons from previous evaluations:\n"
    system_content += "\n".join(f"- {lesson}" for lesson in lessons)

messages = load_memory()
messages[0] = {
    "role": "system",
    "content": system_content,
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
    try:
        result = json.loads(completion.choices[0].message.content)
    except json.JSONDecodeError:
        return None
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


def ask_agent(question):
    messages.append({"role": "user", "content": question})
    context = [messages[0]] + messages[1:][-MAX_RECENT_MESSAGES:]
    completion = client.chat.completions.create(
        model="nvidia/nemotron-3-super-120b-a12b",
        messages=context,
        temperature=0.5,
        max_tokens=1024,
    )
    answer = completion.choices[0].message.content
    lesson = review_answer(question, answer)
    active_lessons = lessons.copy()
    if lesson is not None:
        active_lessons.append(lesson)
        if lesson not in lessons:
            lessons.append(lesson)
        save_lessons(lessons)
        print(f"Lesson saved: {lesson}")
    if active_lessons:
        answer = revise_answer(question, answer, "\n".join(active_lessons))
    messages.append({"role": "assistant", "content": answer})
    save_memory(messages)
    return answer


while True:
    question = input("You: ")
    if question.lower() in {"quit", "exit"}:
        save_memory(messages)
        break
    print(f"Agent: {ask_agent(question)}")
