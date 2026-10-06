from os import getenv
from functools import lru_cache
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

MODEL = "nvidia/nemotron-3-super-120b-a12b"

@lru_cache(maxsize=1)
def get_client():
    api_key = getenv("API")
    if not api_key:
        raise ValueError("Set API in .env to your NVIDIA API key.")
    return OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_key)


def chat_completion(messages, temperature=0.2, max_tokens=2048, tools=None, tool_choice=None):
    options = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools is not None:
        options["tools"] = tools
    if tool_choice is not None:
        options["tool_choice"] = tool_choice
    return get_client().chat.completions.create(**options)


def call_model(messages, temperature=0.2, max_tokens=2048):
    completion = chat_completion(messages, temperature, max_tokens)
    return completion.choices[0].message.content or ""
