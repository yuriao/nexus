"""
Supervisor node: initialises the research state and sets up the run.
Runs first, prepares context for the researcher.
"""
import logging

from langchain_core.messages import SystemMessage

from ..state import ResearchState

logger = logging.getLogger(__name__)


def supervisor_node(state: ResearchState) -> dict:
    """
    Initialise the pipeline:
    - Validate state
    - Set iteration counter
    - Add a system message briefing the pipeline on the task
    """
    company_id = state.get("company_id", "")
    company_name = state.get("company_name", "Unknown Company")
    data_points = state.get("raw_data_points", [])

    logger.info(
        "Supervisor: starting pipeline for company=%s (%s), data_points=%d",
        company_id, company_name, len(data_points),
    )

    system_msg = SystemMessage(
        content=(
            f"You are running a competitive intelligence research pipeline for: {company_name} "
            f"(ID: {company_id}).\n\n"
            f"You have access to {len(data_points)} pre-collected data points from scrapers.\n"
            "The pipeline will: gather research → analyse trends → write a report → critique it.\n"
            "Be thorough, fact-based, and cite sources where possible."
        )
    )

    return {
        "iteration": 0,
        "research_notes": [],
        "analysis": {},
        "draft_report": "",
        "critique": [],
        "final_report": {},
        "confidence_score": 0.0,
        "messages": [system_msg],
    }
