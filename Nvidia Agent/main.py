from openai import OpenAI
from dotenv import load_dotenv
from os import getenv

load_dotenv()

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=getenv("API"),
)


def ask_agent(question):
    completion = client.chat.completions.create(
        model="nvidia/nemotron-3-super-120b-a12b",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": question},
        ],
        temperature=0.5,
        max_tokens=1024,
    )
    return completion.choices[0].message.content


while True:
    question = input("You: ")
    if question.lower() in {"quit", "exit"}:
        break
    print(f"Agent: {ask_agent(question)}")
