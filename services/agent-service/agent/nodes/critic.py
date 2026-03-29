"""
Critic node: fact-checks the report, flags issues, and assigns a confidence score.
"""
import logging
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..state import ResearchState

logger = logging.getLogger(__name__)

CRITIC_SYSTEM = """You are a rigorous fact-checker and quality reviewer for competitive intelligence reports.

Your task is to review the draft report and flag any quality issues.

Check for:
1. UNSUPPORTED CLAIMS — assertions made without cited evidence
2. MISSING DATA — important areas that should have been researched but weren't
3. VAGUE STATEMENTS — non-specific claims that add no intelligence value (e.g. "the company is growing")
4. LOW-CONFIDENCE ASSERTIONS — speculation presented as fact
5. INTERNAL INCONSISTENCIES — contradictions within the report
6. MISSING SECTIONS — required sections that are absent or too thin

Your output format must be EXACTLY:

ISSUES:
- [issue 1]
- [issue 2]
(or "ISSUES: None" if the report is acceptable)

CONFIDENCE_SCORE: [0.00-1.00]
(0.0 = completely unreliable, 1.0 = excellent quality)

VERDICT: [APPROVE | REVISE]
(APPROVE if confidence >= 0.75 and no critical issues; REVISE otherwise)
"""


def critic_node(state: ResearchState) -> dict:
    """Review the draft report and produce a critique with confidence score."""
    company_name = state["company_name"]
    draft_report = state.get("draft_report", "")
    iteration = state.get("iteration", 1)

    if not draft_report:
        logger.warning("Critic: empty draft report for %s", company_name)
        return {
            "critique": ["Empty report — nothing to review"],
            "confidence_score": 0.0,
        }

    model_name = state.get("model_name", "moonshot-v1-32k")
    llm = ChatOpenAI(
        model=model_name,
        temperature=0.0,  # Deterministic for fact-checking
        openai_api_key=os.environ.get("MOONSHOT_API_KEY", os.environ.get("OPENAI_API_KEY")),
        base_url=os.environ.get("OPENAI_BASE_URL"),
    )

    messages = [
        SystemMessage(content=CRITIC_SYSTEM),
        HumanMessage(
            content=(
                f"Review this competitive intelligence report about {company_name} "
                f"(iteration {iteration}):

"
                f"---
{draft_report}
---

"
                "Identify all quality issues and assign a confidence score."
            )
        ),
    ]

    critique = []
    confidence_score = 0.5
    final_report = {}

    try:
        response = llm.invoke(messages)
        content = response.content

        # Parse issues
        issues_match = re.search(
            r"ISSUES:\s*
((?:\s*[-•*]\s*.+
?)*|None)",
            content,
            re.IGNORECASE,
        )
        if issues_match:
            raw_issues = issues_match.group(1).strip()
            if raw_issues.lower() != "none":
                critique = [
                    re.sub(r"^[-•*]\s*", "", line).strip()
                    for line in raw_issues.split("
")
                    if line.strip() and not line.strip().lower() == "none"
                ]

        # Parse confidence score
        conf_match = re.search(r"CONFIDENCE_SCORE:\s*([\d.]+)", content, re.IGNORECASE)
        if conf_match:
            confidence_score = min(1.0, max(0.0, float(conf_match.group(1))))

        # Parse verdict
        verdict_match = re.search(r"VERDICT:\s*(APPROVE|REVISE)", content, re.IGNORECASE)
        verdict = verdict_match.group(1).upper() if verdict_match else "REVISE"

        logger.info(
            "Critic: %s — verdict=%s, confidence=%.2f, issues=%d (iteration %d)",
            company_name, verdict, confidence_score, len(critique), iteration,
        )

        # If approved, package the final report
        if verdict == "APPROVE" or confidence_score >= 0.75:
            analysis = state.get("analysis", {})
            final_report = {
                "summary": _extract_executive_summary(draft_report),
                "full_text": draft_report,
                "opportunities": analysis.get("opportunities", []),
                "risks": analysis.get("risks", []),
                "predictions": _extract_predictions(draft_report),
                "confidence_score": confidence_score,
                "iterations": iteration,
            }

    except Exception as exc:
        logger.error("Critic node error: %s", exc)
        critique = [f"Critique failed: {exc}"]
        confidence_score = 0.0

    return {
        "critique": critique,
        "confidence_score": confidence_score,
        "final_report": final_report,
        "messages": [
            HumanMessage(
                content=f"[Critic] Score: {confidence_score:.2f}, Issues: {len(critique)}"
            )
        ],
    }


def _extract_executive_summary(report_text: str) -> str:
    """Extract the Executive Summary section from the report."""
    match = re.search(
        r"##\s*Executive Summary\s*
(.*?)(?=
##|\Z)",
        report_text,
        re.DOTALL | re.IGNORECASE,
    )
    return match.group(1).strip() if match else report_text[:500]


def _extract_predictions(report_text: str) -> list[str]:
    """Extract the Predictions section as a list."""
    match = re.search(
        r"##\s*Predictions?\s*
(.*?)(?=
##|\Z)",
        report_text,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return []
    section = match.group(1)
    items = re.findall(r"[-•*\d.]\s*(.+?)(?=
[-•*\d]|\Z)", section, re.DOTALL)
    return [item.strip() for item in items if len(item.strip()) > 10]
