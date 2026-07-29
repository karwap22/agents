import os
from langchain_openai import ChatOpenAI

from langchain.agents import create_agent
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

open_router_key = os.environ["OPENROUTER_API_KEY"]

llm = ChatOpenAI(
    model="openai/gpt-oss-120b:free",
    openai_api_key=open_router_key,
    openai_api_base="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "http://localhost:3000", # Can be your site or localhost
        "X-Title": "LangChain Agent Test",       # Your app name
    }
)

@tool
def calculate_circle_area(radius: float) -> str:
    """Use this tool to calculate the area of a circle when given a radius."""
    import math
    area = math.pi * (radius ** 2)
    return f"The area of a circle with radius {radius} is {area:.2f}"

tools = [calculate_circle_area]

agent_executor = create_agent(model=llm, tools=tools)


query = "I have a sqaure with a side of 8 inches. What is its total area?"

print(f"User input - {query}")

input = {
    "messages": [("user",query)]
}

for chunk in agent_executor.stream(input,stream_mode="values"):
    message = chunk["messages"][-1]
    if message.content:
        print(f"Agent: {message.content}")
    elif hasattr(message, "tool_calls") and message.tool_calls:
        print(f"Agent: [Calling Tool: {message.tool_calls[0]['name']} with args {message.tool_calls[0]['args']}]")
