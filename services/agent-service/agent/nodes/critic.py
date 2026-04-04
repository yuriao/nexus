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

CRITIC_SYSTEM = """You are a rigorous quality reviewer for competitive intelligence reports, applying the SCIP/Gartner/McKinsey standard.

Review the draft report against this checklist:

STRUCTURE (mark MISSING if absent):
- [ ] Executive Summary: leads with key finding (not background), has 3 paragraphs, 150-250 words
- [ ] Company Snapshot: structured facts block present
- [ ] Market Position & Competitive Landscape: names at least 2-3 specific competitors
- [ ] SWOT Analysis: 4 quadrants with min 3 points each
- [ ] Key Findings: 5-8 numbered findings with observation + implication each
- [ ] Opportunities: each has timeframe + confidence level
- [ ] Risks & Threats: each has likelihood + impact + mitigation
- [ ] Strategic Predictions: each is falsifiable with confidence % + supporting signal
- [ ] Data Sources & Methodology: present

CONTENT QUALITY (flag each violation):
- VAGUE: Any SWOT point without specific data (e.g. "strong brand" with no metric)
- VAGUE: Any finding that states observation but no implication
- MISSING_DATA: Opportunities without timeframe or confidence
- MISSING_DATA: Risks without likelihood/impact/mitigation
- MISSING_DATA: Predictions without confidence % or supporting signal
- UNSUPPORTED: Claims presented as fact without a source or signal
- FILLER: Sentences that repeat information from another section
- GENERIC: Executive summary starts with "This report..." or similar meta-text

Your output format must be EXACTLY:

ISSUES:
- [specific issue with section name and what is wrong]
(or "ISSUES: None" if the report passes all checks)

CONFIDENCE_SCORE: [0.00-1.00]
(0.0 = major sections missing/all vague, 1.0 = all checks pass with specific data throughout)

VERDICT: [APPROVE | REVISE]
(APPROVE only if: confidence >= 0.75 AND no MISSING sections AND fewer than 2 VAGUE flags)
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

    model_name = state.get("model_name", "moonshot-v1-8k")
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
                f"(iteration {iteration}):\n\n"
                f"---\n{draft_report}\n---\n\n"
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
            r"ISSUES:\s*\n((?:\s*[-•*]\s*.+\n?)*|None)",
            content,
            re.IGNORECASE,
        )
        if issues_match:
            raw_issues = issues_match.group(1).strip()
            if raw_issues.lower() != "none":
                critique = [
                    re.sub(r"^[-•*]\s*", "", line).strip()
                    for line in raw_issues.split("\n")
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
        r"##\s*Executive Summary\s*\n(.*?)(?=\n##|\Z)",
        report_text,
        re.DOTALL | re.IGNORECASE,
    )
    return match.group(1).strip() if match else report_text[:500]


def _extract_predictions(report_text: str) -> list[str]:
    """Extract the Predictions section as a list."""
    match = re.search(
        r"##\s*Predictions?\s*\n(.*?)(?=\n##|\Z)",
        report_text,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return []
    section = match.group(1)
    items = re.findall(r"[-•*\d.]\s*(.+?)(?=\n[-•*\d]|\Z)", section, re.DOTALL)
    return [item.strip() for item in items if len(item.strip()) > 10]
