"""
Researcher node: gathers intelligence using web search and collected data.
Produces a list of research_notes that the analyst will use.
"""
import logging
import os

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from ..state import ResearchState
from ..tools.db_tools import query_collected_data
from ..tools.search_tools import fetch_url, web_search

logger = logging.getLogger(__name__)

RESEARCHER_SYSTEM = """You are a senior competitive intelligence research analyst.

Your task is to gather comprehensive intelligence about the company: {company_name} (ID: {company_id}).

You have access to these tools:
- web_search: Search for recent news and public information
- fetch_url: Read the full content of a URL
- query_collected_data: Query pre-scraped data from our database

Research priorities:
1. Recent news and announcements (last 90 days)
2. Product launches, partnerships, acquisitions
3. Leadership changes
4. Financial indicators (funding, revenue hints, layoffs)
5. Job postings trends (growth areas)
6. Customer sentiment and reviews
7. Competitive positioning

{critique_context}

After gathering information, summarize your key findings as a numbered list of research notes.
Each note should be specific, factual, and include the source.
"""


def researcher_node(state: ResearchState) -> dict:
    """Run the researcher agent with web search and DB query tools."""
    company_id = state["company_id"]
    company_name = state["company_name"]
    iteration = state.get("iteration", 0)
    critique = state.get("critique", [])

    # If this is a re-run after critique, add context about what to fix
    critique_context = ""
    if critique and iteration > 0:
        issues = "\n".join(f"- {c}" for c in critique)
        critique_context = (
            f"\n\nPrevious critique found these issues that need more research:\n{issues}\n"
            "Focus on addressing these gaps in this iteration."
        )

    model_name = state.get("model_name", "moonshot-v1-8k")
    llm = ChatOpenAI(
        model=model_name,
        temperature=0.1,
        openai_api_key=os.environ.get("MOONSHOT_API_KEY", os.environ.get("OPENAI_API_KEY")),
        base_url=os.environ.get("OPENAI_BASE_URL"),
    )

    tools = [web_search, fetch_url, query_collected_data]
    llm_with_tools = llm.bind_tools(tools)

    # Build initial prompt
    prompt = RESEARCHER_SYSTEM.format(
        company_name=company_name,
        company_id=company_id,
        critique_context=critique_context,
    )

    messages = state.get("messages", [])
    user_msg = HumanMessage(
        content=(
            f"Research {company_name} thoroughly. "
            f"Use the available tools to gather intelligence. "
            f"Iteration: {iteration + 1}. "
            f"Start by querying our collected data with query_collected_data('{company_id}'), "
            f"then supplement with web_search for recent developments."
        )
    )

    from langchain_core.messages import SystemMessage
    research_messages = [SystemMessage(content=prompt), user_msg]

    # Agentic loop: keep calling until no more tool calls
    max_steps = 8
    research_notes = []

    try:
        for step in range(max_steps):
            response = llm_with_tools.invoke(research_messages)
            research_messages.append(response)

            if not response.tool_calls:
                # Extract the final research notes from the response
                content = response.content
                if isinstance(content, str):
                    # Parse numbered list items as individual notes
                    import re
                    notes = re.findall(r"\d+\.\s+(.+?)(?=\n\d+\.|\Z)", content, re.DOTALL)
                    research_notes = [n.strip() for n in notes if len(n.strip()) > 20]
                    if not research_notes and content:
                        # Fallback: split by newlines
                        research_notes = [
                            line.strip() for line in content.split("\n")
                            if len(line.strip()) > 30
                        ]
                break

            # Handle tool calls
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                logger.info("Researcher calling tool: %s(%s)", tool_name, list(tool_args.keys()))

                tool_map = {
                    "web_search": web_search,
                    "fetch_url": fetch_url,
                    "query_collected_data": query_collected_data,
                }
                if tool_name in tool_map:
                    from langchain_core.messages import ToolMessage
                    try:
                        result = tool_map[tool_name].invoke(tool_args)
                        research_messages.append(
                            ToolMessage(
                                content=str(result)[:3000],
                                tool_call_id=tool_call["id"],
                            )
                        )
                    except Exception as exc:
                        research_messages.append(
                            ToolMessage(
                                content=f"Tool error: {exc}",
                                tool_call_id=tool_call["id"],
                            )
                        )

    except Exception as exc:
        logger.error("Researcher node error: %s", exc)
        research_notes = [f"Research encountered an error: {exc}"]

    logger.info(
        "Researcher completed for %s: %d notes (iteration %d)",
        company_name, len(research_notes), iteration + 1,
    )

    return {
        "research_notes": research_notes,
        "iteration": iteration + 1,
        "messages": research_messages[1:],  # Skip the system message (already in state)
    }
