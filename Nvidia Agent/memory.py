import json
import re
from datetime import datetime

from config import FACTS_FILE, LESSONS_FILE, MAX_RECENT_MESSAGES, MEMORY_FILE
from llm import call_model
from tracing import trace


SYSTEM_MESSAGE = {"role": "system", "content": "You are a helpful assistant."}
SENSITIVE_KEYWORDS = {
    "password", "secret", "token", "api_key", "ssn", "credit_card",
    "bank", "medical", "health", "passport", "license",
}


class Memory:
    def __init__(self):
        self.lessons = self._load_lessons()
        self.facts = self._load_facts()
        self.messages = self._load_messages()
        self.save_facts()
        self.messages[0] = {"role": "system", "content": self.build_system_content()}

    @staticmethod
    def _load_json(path, default):
        try:
            with open(path) as file:
                return json.load(file)
        except FileNotFoundError:
            return default

    def _load_messages(self):
        return self._load_json(MEMORY_FILE, [SYSTEM_MESSAGE])

    def _load_lessons(self):
        return self._load_json(LESSONS_FILE, [])

    def _load_facts(self):
        stored = self._load_json(FACTS_FILE, [])
        facts = []
        for fact in stored:
            if isinstance(fact, str):
                fact = {"key": "legacy", "value": fact}
            if not isinstance(fact, dict):
                continue
            fact.setdefault("source", "user")
            fact.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
            fact.setdefault("updated_at", fact["created_at"])
            facts.append(fact)
        return facts

    def save_messages(self):
        with open(MEMORY_FILE, "w") as file:
            json.dump(self.messages, file, indent=2)

    def save_lessons(self):
        with open(LESSONS_FILE, "w") as file:
            json.dump(self.lessons, file, indent=2)

    def save_facts(self):
        with open(FACTS_FILE, "w") as file:
            json.dump(self.facts, file, indent=2)

    def build_system_content(self, selected_facts=None):
        selected_facts = self.facts if selected_facts is None else selected_facts
        content = "You are a helpful assistant."
        if selected_facts:
            content += "\n\nKnown facts about the user (authoritative over conflicting conversation history):\n"
            content += "\n".join(f"- {fact['key']}: {fact['value']}" for fact in selected_facts)
        if self.lessons:
            content += "\n\nUseful lessons from previous evaluations:\n"
            content += "\n".join(f"- {lesson}" for lesson in self.lessons)
        return content

    def relevant_facts(self, question):
        stop_words = {"a", "an", "the", "is", "my", "what", "where", "who", "how"}
        question_words = set(re.findall(r"[a-z0-9]+", question.lower())) - stop_words
        return [
            fact for fact in self.facts
            if question_words & set(re.findall(r"[a-z0-9]+", f"{fact['key']} {fact['value']}".lower()))
        ]

    def semantic_relevant_facts(self, question):
        if not self.facts:
            return []
        catalog = [{"key": fact["key"], "value": fact["value"]} for fact in self.facts]
        response = call_model(
            [
                {"role": "system", "content": "Select relevant fact keys by meaning. Return JSON only: {\"keys\": [\"key\"]}. Use only catalog keys."},
                {"role": "user", "content": f"Question: {question}\nFact catalog: {json.dumps(catalog)}"},
            ],
            temperature=0,
            max_tokens=100,
        )
        from utils import parse_json
        result = parse_json(response)
        keys = result.get("keys") if isinstance(result, dict) else []
        selected = [fact for fact in self.facts if isinstance(keys, list) and fact["key"] in keys]
        trace("semantic_lookup", {"keys": [fact["key"] for fact in selected]})
        return selected

    def select_relevant_facts(self, question):
        return self.relevant_facts(question) or self.semantic_relevant_facts(question)

    def build_context(self, selected_facts):
        history = self.messages[1:-1][-MAX_RECENT_MESSAGES:]
        if selected_facts:
            fact_words = {word for fact in selected_facts for word in re.findall(r"[a-z0-9]+", fact["key"].lower())}
            history = [message for message in history if not fact_words & set(re.findall(r"[a-z0-9]+", message["content"].lower()))]
        return [self.messages[0]] + history + [self.messages[-1]]

    def make_fact(self, key, value, source="user"):
        timestamp = datetime.now().isoformat(timespec="seconds")
        return {"key": key, "value": value, "source": source, "created_at": timestamp, "updated_at": timestamp}

    def is_sensitive(self, fact):
        return any(keyword in fact["key"].lower() for keyword in SENSITIVE_KEYWORDS)

    def add_or_update_fact(self, fact, source="user"):
        existing = next((item for item in self.facts if item["key"] == fact["key"]), None)
        if existing is None:
            self.facts.append(self.make_fact(fact["key"], fact["value"], source))
            return "saved"
        if existing["value"] == fact["value"]:
            return "unchanged"
        existing.update(value=fact["value"], source=source, updated_at=datetime.now().isoformat(timespec="seconds"))
        return "updated"
