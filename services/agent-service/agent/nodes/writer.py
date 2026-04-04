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

WRITER_SYSTEM = """You are an expert competitive intelligence analyst producing reports to industry-standard (SCIP/Gartner/McKinsey framework).

Your report MUST follow this exact structure and quality bar:

---

## Executive Summary
3 tight paragraphs (150-250 words total):
- Para 1: Company's current market position + one compelling hook stat/finding
- Para 2: The 3 most important insights (McKinsey Rule of 3) — be specific
- Para 3: Clear strategic implication — what should the reader DO?
NEVER start with "This report analyzes..." — lead with the most important finding.

## Company Snapshot
Structured facts (not paragraphs): Founded, HQ, Employees, Revenue (est.), Core Products, Primary Markets, Business Model, Key Leadership, Funding/Ownership.

## Market Position & Competitive Landscape
200-350 words: Market tier (leader/challenger/niche/disruptor), top 3 competitors, differentiation, estimated market share or growth, competitive moat.

## SWOT Analysis
4 quadrants, minimum 3 SPECIFIC evidence-backed points each. NO generic statements.
❌ "Strong brand" → ✅ "Brand NPS of 72 vs industry avg 45"

## Key Findings
5-8 numbered findings. Each MUST follow:
**[Finding title]:** [Specific observation with data]. [Why it matters / strategic implication].

## Opportunities
3-5 numbered. Each MUST include: description + Timeframe (immediate/6mo/12mo+) + Confidence (H/M/L).

## Risks & Threats
3-5 numbered. Each MUST include: description + Likelihood (H/M/L) + Impact (H/M/L) + Mitigation suggestion.

## Strategic Predictions (6-12 Month Outlook)
3-5 numbered falsifiable predictions. Each MUST include: specific outcome + timeframe + Confidence % + supporting signal/evidence.
❌ "Will grow" → ✅ "Will launch enterprise tier by Q3 2026 (75% confidence) — signalled by 4 enterprise job postings in Jan 2026"

## Data Sources & Methodology
Bullet list: sources used, date range, data gaps, overall confidence (High/Medium/Low).

---

QUALITY RULES (non-negotiable):
- Every section must contain at least one specific number or metric
- All SWOT points must be specific and evidence-backed
- All predictions must be falsifiable with a confidence % and a supporting signal
- Use **bold** for key terms and findings
- Professional, direct, third-person tone. No hedging like "it seems" or "perhaps"
- Prefix low-confidence claims with: ⚠️ Low confidence:
- Total length: 800-1,500 words
- If critique was provided, explicitly fix every issue raised
"""


def writer_node(state: ResearchState) -> dict:
    """Synthesise research and analysis into a full report draft."""
    company_name = state["company_name"]
    research_notes = state.get("research_notes", [])
    analysis = state.get("analysis", {})
    critique = state.get("critique", [])
    iteration = state.get("iteration", 1)

    model_name = state.get("model_name", "moonshot-v1-8k")
    llm = ChatOpenAI(
        model=model_name,
        temperature=0.2,
        openai_api_key=os.environ.get("MOONSHOT_API_KEY", os.environ.get("OPENAI_API_KEY")),
        base_url=os.environ.get("OPENAI_BASE_URL"),
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
