"""
Nexus LangGraph pipeline: the core multi-agent research graph.

Flow:
  START → supervisor → researcher → analyst → writer → critic
                            ↑                              |
                            └─── (should_redo_research) ──┘
                                          |
                                       (done)
                                          |
                                         END

Decision at critic:
  - If iteration < max_iterations AND critique has issues → back to researcher
  - Otherwise → END
"""
from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import END, START, StateGraph

from .nodes.analyst import analyst_node
from .nodes.critic import critic_node
from .nodes.researcher import researcher_node
from .nodes.supervisor import supervisor_node
from .nodes.writer import writer_node
from .state import ResearchState

logger = logging.getLogger(__name__)


# ─── Conditional edge ────────────────────────────────────────────────────────

def should_redo_research(state: ResearchState) -> Literal["researcher", "__end__"]:
    """
    After critic runs: decide whether to loop back to researcher or end.
    Loops back if:
      1. There are unresolved critique issues, AND
      2. We haven't hit max_iterations
    """
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 3)
    critique = state.get("critique", [])
    confidence = state.get("confidence_score", 0.0)

    # Acceptable quality threshold
    if confidence >= 0.75 and len(critique) == 0:
        logger.info("Critic satisfied (confidence=%.2f). Ending pipeline.", confidence)
        return END

    if iteration >= max_iter:
        logger.info(
            "Max iterations (%d) reached. Ending pipeline with confidence=%.2f.",
            max_iter, confidence,
        )
        return END

    logger.info(
        "Critic found %d issues (confidence=%.2f). Looping back. Iteration %d/%d.",
        len(critique), confidence, iteration, max_iter,
    )
    return "researcher"


# ─── Graph definition ────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Construct and compile the Nexus research StateGraph."""
    workflow = StateGraph(ResearchState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("critic", critic_node)

    # Entry edge
    workflow.add_edge(START, "supervisor")

    # Linear pipeline
    workflow.add_edge("supervisor", "researcher")
    workflow.add_edge("researcher", "analyst")
    workflow.add_edge("analyst", "writer")
    workflow.add_edge("writer", "critic")

    # Conditional exit from critic
    workflow.add_conditional_edges(
        "critic",
        should_redo_research,
        {
            "researcher": "researcher",
            END: END,
        },
    )

    return workflow.compile()


# Module-level compiled graph (cached)
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
        logger.info("LangGraph pipeline compiled")
    return _graph
