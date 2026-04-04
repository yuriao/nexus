"""
ResearchState: the shared state TypedDict for the LangGraph pipeline.
All nodes read from and write to this state.
"""
from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ResearchState(TypedDict):
    # ── Identity ──────────────────────────────────────────────────────────────
    company_id: str
    company_name: str
    report_id: str                      # UUID of the ResearchReport being generated

    # ── Data ──────────────────────────────────────────────────────────────────
    raw_data_points: list[dict]        # Loaded from MySQL at task start
    research_notes: list[str]          # Written by researcher node
    analysis: dict                      # Written by analyst node

    # ── Report draft ──────────────────────────────────────────────────────────
    draft_report: str                   # Written by writer node (markdown)
    critique: list[str]                 # Written by critic node (list of issues)
    final_report: dict                  # Finalised by writer after critique passes

    # ── Metrics ───────────────────────────────────────────────────────────────
    metrics: list[dict]                 # Written by metrics node (20 standard metrics)
    metrics_calculated_at: str          # ISO timestamp of metrics calculation

    # ── Control ───────────────────────────────────────────────────────────────
    iteration: int                      # How many researcher→analyst→writer→critic loops
    max_iterations: int                 # Maximum loops before forcing completion
    confidence_score: float             # Assigned by critic (0.0 – 1.0)
    model_name: str                     # LLM model name (e.g. "moonshot-v1-8k")

    # ── Messages (LangGraph managed) ─────────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]
