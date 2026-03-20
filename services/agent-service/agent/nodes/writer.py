"""
Writer node: synthesises research notes and analysis into a structured report.
"""
import logging
import os
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..state import ResearchState

logger = logging.getLogger(__name__)

WRITER_SYSTEM = """You are an expert competitive intelligence report writer.

Your task is to synthesise research and analysis into a structured, professional report.

The report must include these sections:

## Executive Summary
A 2-3 paragraph overview of the key findings and strategic implications.

## Key Findings
5-10 specific, evidence-backed findings about the company.

## Opportunities
Specific opportunities for competitors or market participants, based on identified gaps/weaknesses.

## Risks / Threats
Specific risks or threats posed by this company, based on strengths and momentum signals.

## Predictions
3-5 forward-looking predictions for the next 6-12 months based on current signals.

## Methodology
Brief note on data sources and confidence level.

Guidelines:
- Be specific and evidence-based. Avoid vague statements.
- Cite sources (URLs, data types) where possible.
- Flag any claims with low confidence.
- Write in professional business English.
- If critique was provided, explicitly address each issue.
"""


def writer_node(state: ResearchState) -> dict:
    """Synthesise research and analysis into a full report draft."""
    company_name = state["company_name"]
    research_notes = state.get("research_notes", [])
    analysis = state.get("analysis", {})
    critique = state.get("critique", [])
    iteration = state.get("iteration", 1)

    model_name = state.get("model_name", "gpt-4o")
    llm = ChatOpenAI(
        model=model_name,
        temperature=0.2,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
    )

    notes_text = "\n".join(f"- {n}" for n in research_notes)
    opps = "\n".join(f"- {o}" for o in analysis.get("opportunities", []))
    risks = "\n".join(f"- {r}" for r in analysis.get("risks", []))
    trends = "\n".join(f"- {t}" for t in analysis.get("trends", []))

    critique_section = ""
    if critique and iteration > 1:
        issues = "\n".join(f"- {c}" for c in critique)
        critique_section = (
            f"\n\nPrevious critique issues to address in this revision:\n{issues}\n"
            "Make sure to explicitly fix each of these issues."
        )

    user_content = f"""Write a competitive intelligence report for: {company_name}

RESEARCH NOTES:
{notes_text}

ANALYSIS:
Opportunities:
{opps}

Risks:
{risks}

Trends:
{trends}

Analyst Confidence: {analysis.get('confidence', 0) * 100:.0f}%
{critique_section}

Date: {datetime.now(timezone.utc).strftime('%B %d, %Y')}

Write the full report now."""

    messages = [
        SystemMessage(content=WRITER_SYSTEM),
        HumanMessage(content=user_content),
    ]

    draft_report = ""
    try:
        response = llm.invoke(messages)
        draft_report = response.content
        logger.info(
            "Writer completed report for %s (%d chars, iteration %d)",
            company_name, len(draft_report), iteration,
        )
    except Exception as exc:
        logger.error("Writer node error: %s", exc)
        draft_report = f"# Report for {company_name}\n\nError generating report: {exc}"

    return {
        "draft_report": draft_report,
        "messages": [HumanMessage(content=f"[Writer] Draft report generated ({len(draft_report)} chars)")],
    }
