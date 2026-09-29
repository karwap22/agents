from llm import call_model
from memory import Memory
from tracing import trace
from utils import parse_json


class Agent:
    def __init__(self, memory):
        self.memory = memory

    def review_answer(self, question, answer):
        response = call_model(
            [
                {"role": "system", "content": "Review the answer. Return JSON only: {\"lesson\": \"one short actionable lesson\"} or {\"lesson\": null}."},
                {"role": "user", "content": f"Question: {question}\nAnswer: {answer}"},
            ],
            temperature=0,
            max_tokens=100,
        )
        result = parse_json(response)
        lesson = result.get("lesson") if isinstance(result, dict) else None
        return lesson.strip() if isinstance(lesson, str) and lesson.strip() else None

    def revise_answer(self, question, answer, lesson):
        response = call_model(
            [
                {"role": "system", "content": "Improve the draft using the lesson. Return only the final answer."},
                {"role": "user", "content": f"Question: {question}\nDraft answer: {answer}\nLesson: {lesson}"},
            ],
            temperature=0.3,
            max_tokens=1024,
        )
        return response.strip() or answer

    def extract_facts(self, question):
        response = call_model(
            [
                {"role": "system", "content": "Extract only durable facts explicitly stated by the user. Return JSON only: {\"facts\": [{\"key\": \"...\", \"value\": \"...\"}]} or {\"facts\": []}. Use stable snake_case keys. Do not infer from an assistant answer."},
                {"role": "user", "content": f"User message: {question}"},
            ],
            temperature=0,
            max_tokens=150,
        )
        result = parse_json(response)
        facts = result.get("facts") if isinstance(result, dict) else []
        if not isinstance(facts, list):
            return []
        return [
            {"key": item["key"].strip(), "value": item["value"].strip()}
            for item in facts
            if isinstance(item, dict)
            and isinstance(item.get("key"), str)
            and isinstance(item.get("value"), str)
            and item["key"].strip()
            and item["value"].strip()
        ]

    def ask(self, question):
        trace("input_received", {"length": len(question)})
        self.memory.messages.append({"role": "user", "content": question})
        selected = self.memory.select_relevant_facts(question)
        trace("facts_selected", {"keys": [fact["key"] for fact in selected]})
        self.memory.messages[0]["content"] = self.memory.build_system_content(selected)
        context = self.memory.build_context(selected)
        trace("context_built", {"message_count": len(context)})
        answer = call_model(context, temperature=0.5, max_tokens=1024)
        trace("draft_completed", {"length": len(answer)})
        lesson = self.review_answer(question, answer)
        trace("review_completed", {"lesson_found": lesson is not None})
        if lesson is not None:
            if lesson not in self.memory.lessons and lesson not in self.memory.candidates:
                self.memory.candidates.append(lesson)
                self.memory.save_candidates()
                print(f"Candidate lesson saved: {lesson}")
            answer = self.revise_answer(question, answer, lesson)
            trace("revision_completed", {"performed": True, "length": len(answer)})
        else:
            trace("revision_completed", {"performed": False})
        added = []
        for fact in self.extract_facts(question):
            if self.memory.is_sensitive(fact):
                print(f"Sensitive fact not saved automatically: {fact['key']}. Use /remember to save it explicitly.")
                continue
            status = self.memory.add_or_update_fact(fact)
            if status != "unchanged":
                added.append(fact["key"])
                print(f"Fact {status}: {fact['key']} = {fact['value']}")
        trace("fact_extraction_completed", {"keys": added})
        if self.memory.facts:
            self.memory.save_facts()
            self.memory.messages[0]["content"] = self.memory.build_system_content()
        self.memory.messages.append({"role": "assistant", "content": answer})
        self.memory.save_messages()
        trace("memory_saved")
        return answer
