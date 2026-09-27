from os import getenv

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=getenv("API"),
)
MODEL = "nvidia/nemotron-3-super-120b-a12b"


def call_model(messages, temperature=0.5, max_tokens=1024):
    completion = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return completion.choices[0].message.content
