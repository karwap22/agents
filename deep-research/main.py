from dotenv import load_dotenv
from os import getenv
from typing import Annotated, Literal
import httpx
from langchain.tools import InjectedToolArg, tool
from markdownify import markdownify
from tavily import TavilyClient
from langchain.agents.middleware import TodoListMiddleware

load_dotenv()
gemini_api_key = getenv("GOOGLE_API_KEY")
tavily_api_key = getenv("TAVILY_API_KEY")

tavily_client = TavilyClient(api_key = tavily_api_key)


def fetch_webpage_content(url: str, timeout: float = 10.0) -> str:
    """Fetch webpage and convert HTML to markdown."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        response = httpx.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return markdownify(response.text)
    except Exception as e:
        return f"Error fetching {url}: {e!s}"


@tool(parse_docstring=True)
def tavily_search(
    query: str,
    max_results: Annotated[int, InjectedToolArg] = 1,
    topic: Annotated[
        Literal["general", "news", "finance"], InjectedToolArg
    ] = "general",
) -> str:
    """Search the web for information on a given query.

    Uses Tavily to discover relevant URLs, then fetches and returns full webpage content as markdown.

    Args:
        query: Search query to execute
        max_results: Maximum number of results to return (default: 1)
        topic: Topic filter - 'general', 'news', or 'finance' (default: 'general')

    Returns:
        Formatted search results with full webpage content
    """

    search_results = tavily_client.search(
        query,
        max_results=max_results,
        topic=topic,
    )
    result_texts = []
    for result in search_results.get("results", []):
        url = result["url"]
        title = result["title"]
        content = fetch_webpage_content(url)
        result_texts.append(f"## {title}\n**URL:** {url}\n\n{content}\n---")

    return f"Found {len(result_texts)} result(s) for '{query}':\n\n" + "\n".join(
        result_texts
    )



from datetime import datetime

from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware
from langchain_google_genai import ChatGoogleGenerativeAI
from prompts import RESEARCH_WORKFLOW_INSTRUCTIONS,RESEARCHER_INSTRUCTIONS,SUBAGENT_DELEGATION_INSTRUCTIONS
max_concurrent_research_units = 3
max_researcher_iterations = 3

current_date = datetime.now().strftime("%Y-%m-%d")

INSTRUCTIONS = (
    RESEARCH_WORKFLOW_INSTRUCTIONS
    + "\n\n"
    + "=" * 80
    + "\n\n"
    + SUBAGENT_DELEGATION_INSTRUCTIONS.format(
        max_concurrent_research_units=max_concurrent_research_units,
        max_researcher_iterations=max_researcher_iterations,
    )
)

research_sub_agent = {
    "name": "research-agent",
    "description": "Delegate research to the sub-agent. Give one topic at a time.",
    "system_prompt": RESEARCHER_INSTRUCTIONS.format(date=current_date),
    "tools": [tavily_search],
}

model = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0.0)

agent = create_deep_agent(
    model=model,
    tools=[tavily_search],
    system_prompt=INSTRUCTIONS,
    subagents=[research_sub_agent],
    middleware=[TodoListMiddleware()],
)


from langchain.messages import HumanMessage

if __name__ == "__main__":
    result = agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content="What are the main differences between RAG and fine-tuning for LLM applications?"
                )
            ]
        }
    )

    for msg in result.get("messages", []):
        if hasattr(msg, "content") and msg.content:
            print(msg.content)
