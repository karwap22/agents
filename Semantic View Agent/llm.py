from os import getenv

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

MODEL = "nvidia/nemotron-3-super-120b-a12b"


def call_model(messages, temperature=0.2, max_tokens=2048):
    api_key = getenv("API")
    if not api_key:
        raise ValueError("Set API in .env to your NVIDIA API key.")
    client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_key)
    completion = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return completion.choices[0].message.content or ""
