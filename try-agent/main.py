from dotenv import load_dotenv
from openai import OpenAI
import os
import json
from tools import get_all_files
load_dotenv()


client = OpenAI(
    api_key=os.environ.get("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)


# -----------------------------
# Tool Registry
# -----------------------------
tool_map = {
    "get_all_files": get_all_files
}

# -----------------------------
# Tool Definitions
# -----------------------------
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_all_files",
            "description": "Gets all the files in the current folder",
            "parameters": {
                "type": "object",
                
            }
        }
    }
]

# -----------------------------
# Agent Loop
# -----------------------------
messages = [
    {
        "role": "system",
        "content": (
            "You are a helpful assistant. "
            "Use tools whenever needed."
        )
    }
]

while True:
    user_input = input("\nYou: ")

    if user_input.lower() in ["quit", "exit"]:
        break

    messages.append({
        "role": "user",
        "content": user_input
    })

    while True:

        response = client.chat.completions.create(
            model=os.environ.get("MODEL"),
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        message = response.choices[0].message

        # Final answer
        if not message.tool_calls:
            print("\nAssistant:", message.content)
            messages.append({
                "role": "assistant",
                "content": message.content
            })
            break

        # Store assistant tool request
        messages.append(message)

        # Execute tools
        for tool_call in message.tool_calls:

            tool_name = tool_call.function.name

            args = json.loads(
                tool_call.function.arguments
            )

            print(f"\nCalling tool: {tool_name}")
            print("Arguments:", args)

            result = tool_map[tool_name](**args)

            print("Result:", result)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result)
            })