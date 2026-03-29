"""
Analyst node: analyses research notes and identifies opportunities, risks, and trends.
"""
import logging
import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..state import ResearchState
from ..tools.analysis_tools import compute_trend
from ..tools.db_tools import query_collected_data

logger = logging.getLogger(__name__)

ANALYST_SYSTEM = """You are a senior financial and market analyst specialising in competitive intelligence.

You have received research notes about {company_name}. Your task is to:

1. Identify key OPPORTUNITIES for competitors or market participants
   (e.g. gaps in their product, losing customers, under-resourced areas)

2. Identify key RISKS / THREATS
   (e.g. they are expanding aggressively, new product that threatens competitors, strong hiring signal)

3. Identify TRENDS
   (e.g. shifting focus, market positioning change, organisational signals)

4. Compute data trends from the collected data points if available.

Be analytical, specific, and actionable. Format your output as:

OPPORTUNITIES:
- [specific opportunity with evidence]

RISKS:
- [specific risk with evidence]

TRENDS:
- [specific trend with evidence]

CONFIDENCE: [0-100]% overall confidence in this analysis based on data quality.
"""


def analyst_node(state: ResearchState) -> dict:
    """Run the analyst: produces structured analysis from research notes."""
    company_id = state["company_id"]
    company_name = state["company_name"]
    research_notes = state.get("research_notes", [])
    raw_data_points = state.get("raw_data_points", [])

    if not research_notes:
        logger.warning("Analyst: no research notes available for %s", company_name)
        return {
            "analysis": {
                "opportunities": [],
                "risks": [],
                "trends": [],
                "confidence": 0.0,
                "error": "No research notes available",
            }
        }

    model_name = state.get("model_name", "moonshot-v1-32k")
    llm = ChatOpenAI(
        model=model_name,
        temperature=0.1,
        openai_api_key=os.environ.get("MOONSHOT_API_KEY", os.environ.get("OPENAI_API_KEY")),
        base_url=os.environ.get("OPENAI_BASE_URL"),
    )

    tools = [compute_trend, query_collected_data]
    llm_with_tools = llm.bind_tools(tools)

    notes_text = "
".join(f"{i+1}. {note}" for i, note in enumerate(research_notes))

    messages = [
        SystemMessage(content=ANALYST_SYSTEM.format(company_name=company_name)),
        HumanMessage(
            content=(
                f"Analyse these research notes about {company_name}:

{notes_text}

"
                f"You also have {len(raw_data_points)} raw data points available via "
                f"query_collected_data('{company_id}') and compute_trend() for trend analysis.

"
                "Produce a structured analysis with opportunities, risks, and trends."
            )
        ),
    ]

    analysis = {
        "opportunities": [],
        "risks": [],
        "trends": [],
        "confidence": 0.0,
        "raw_response": "",
    }

    try:
        max_steps = 5
        for step in range(max_steps):
            response = llm_with_tools.invoke(messages)
            messages.append(response)

            if not response.tool_calls:
                content = response.content
                analysis["raw_response"] = content
                analysis.update(_parse_analyst_response(content))
                break

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                logger.info("Analyst calling tool: %s", tool_name)

                from langchain_core.messages import ToolMessage
                tool_map = {"compute_trend": compute_trend, "query_collected_data": query_collected_data}
                try:
                    result = tool_map[tool_name].invoke(tool_args) if tool_name in tool_map else {}
                    messages.append(ToolMessage(content=str(result)[:2000], tool_call_id=tool_call["id"]))
                except Exception as exc:
                    messages.append(ToolMessage(content=f"Error: {exc}", tool_call_id=tool_call["id"]))

    except Exception as exc:
        logger.error("Analyst node error: %s", exc)
        analysis["error"] = str(exc)

    logger.info("Analyst completed for %s", company_name)
    return {"analysis": analysis, "messages": messages[2:]}


def _parse_analyst_response(content: str) -> dict:
    """Parse structured analyst output into opportunities/risks/trends."""
    import re

    def extract_section(label: str) -> list[str]:
        pattern = rf"{label}:\s*
((?:\s*[-•*]\s*.+
?)+)"
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            lines = match.group(1).strip().split("
")
            return [re.sub(r"^[-•*]\s*", "", l).strip() for l in lines if l.strip()]
        return []

    confidence = 0.5
    conf_match = re.search(r"CONFIDENCE:\s*(\d+)%", content, re.IGNORECASE)
    if conf_match:
        confidence = int(conf_match.group(1)) / 100.0

    return {
        "opportunities": extract_section("OPPORTUNITIES"),
        "risks": extract_section("RISKS"),
        "trends": extract_section("TRENDS"),
        "confidence": confidence,
    }
