"""
Metrics node: extracts 20 standard numeric metrics from research data using LLM.
Follows METRICS_STANDARD.md (CB Insights / Gartner / PitchBook / Bloomberg framework).
"""
import json
import logging
import os
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..state import ResearchState

logger = logging.getLogger(__name__)

METRICS_SYSTEM = """You are a quantitative competitive intelligence analyst.
Your task is to extract or estimate 20 standard numeric metrics for a company from research data.

For each metric, output a JSON object. Use ONLY data found in the research notes.
If a metric cannot be calculated, set value to null and confidence to "unavailable".

Output a JSON array of exactly 20 metric objects with this schema:
{
  "code": "M01",
  "name": "...",
  "value": <number or null>,
  "unit": "...",
  "confidence": "high|medium|low|unavailable",
  "source": "...",
  "note": "..."
}

THE 20 METRICS TO EXTRACT:
M01 Employee Growth Rate 6-month (%)
M02 Job Posting Velocity (jobs/month)
M03 Hiring Focus Score - % of postings in top dept (%)
M04 Revenue Estimate ARR/Annual USD Millions
M05 Funding Total USD Millions
M06 Funding Runway Estimate (months)
M07 Web Traffic Estimate Monthly Visits (millions)
M08 Domain Authority Score (0-100)
M09 App Store Rating (1.0-5.0)
M10 Social Media Followers Total (thousands)
M11 GitHub Activity Score (derived 0-100, null if no public GitHub)
M12 Review Score primary platform (1.0-5.0)
M13 Review Volume 30-day (count)
M14 Sentiment Score (-100 to +100)
M15 Employee Satisfaction Glassdoor (1.0-5.0)
M16 Patent Filing Count 2-year (count, null if not R&D company)
M17 Technology Stack Breadth (count of distinct tech categories)
M18 Product Release Frequency 6-month (count)
M19 News Mention Volume 30-day (count)
M20 Regulatory Legal Risk Score (count of active issues)

CALCULATION RULES:
- M14 Sentiment: classify each research note as positive/negative/neutral. Score = ((pos-neg)/total)*100
- M19 News Mentions: count news-type sources in research notes
- M20 Legal Risk: count any mentions of lawsuits, regulatory actions, fines
- For estimates, use proxy calculations and note the method in "note" field
- Confidence: "high"=official source, "medium"=reputable 3rd party, "low"=proxy estimate

Return ONLY the JSON array, no other text."""


def metrics_node(state: ResearchState) -> dict:
    """Extract 20 standard numeric metrics from research data."""
    company_name = state["company_name"]
    research_notes = state.get("research_notes", [])
    report_id = state.get("report_id", "")

    model_name = state.get("model_name", "moonshot-v1-8k")
    llm = ChatOpenAI(
        model=model_name,
        temperature=0.1,
        openai_api_key=os.environ.get("MOONSHOT_API_KEY", os.environ.get("OPENAI_API_KEY")),
        base_url=os.environ.get("OPENAI_BASE_URL"),
    )

    notes_text = "\n".join(f"[{i+1}] {n}" for i, n in enumerate(research_notes))
    if not notes_text:
        notes_text = "No research data available."

    messages = [
        SystemMessage(content=METRICS_SYSTEM),
        HumanMessage(content=f"""Company: {company_name}
Report ID: {report_id}

RESEARCH NOTES:
{notes_text}

Extract all 20 metrics. Return only the JSON array."""),
    ]

    try:
        response = llm.invoke(messages)
        raw = response.content.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        metrics_list = json.loads(raw)

        # Validate structure
        valid_metrics = []
        for m in metrics_list:
            if isinstance(m, dict) and "code" in m and "value" in m:
                # Ensure value is numeric or null
                if m["value"] is not None:
                    try:
                        m["value"] = float(m["value"])
                    except (TypeError, ValueError):
                        m["value"] = None
                        m["confidence"] = "unavailable"
                valid_metrics.append(m)

        logger.info("Metrics extracted for %s: %d metrics, %d with values",
                    company_name, len(valid_metrics),
                    sum(1 for m in valid_metrics if m.get("value") is not None))

        return {
            "metrics": valid_metrics,
            "metrics_calculated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error("Metrics node error for %s: %s", company_name, e)
        # Return empty metrics rather than failing the pipeline
        return {
            "metrics": [],
            "metrics_calculated_at": datetime.now(timezone.utc).isoformat(),
        }
