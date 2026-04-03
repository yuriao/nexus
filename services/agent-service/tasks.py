"""
Celery tasks for the agent-service.
Runs the LangGraph multi-agent research pipeline.
"""
import json
import logging
import os
from datetime import datetime, timezone

import MySQLdb
from celery_app import app

logger = logging.getLogger(__name__)


def _get_db():
    return MySQLdb.connect(
        host=os.environ.get("DB_HOST", "mysql"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "nexus"),
        passwd=os.environ.get("DB_PASSWORD", "nexus_secret"),
        db=os.environ.get("DB_NAME", "nexus_core"),
        charset="utf8mb4",
    )


def _get_company(company_id: int) -> dict | None:
    db = _get_db()
    try:
        cur = db.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM companies_company WHERE id = %s", (company_id,))
        return cur.fetchone()
    finally:
        db.close()


def _get_data_points(company_id: int, limit: int = 100) -> list[dict]:
    db = _get_db()
    try:
        cur = db.cursor(MySQLdb.cursors.DictCursor)
        cur.execute(
            """SELECT id, source_type, source_url, raw_text, structured_json,
                      extracted_at, confidence_score
               FROM companies_datapoint
               WHERE company_id = %s
               ORDER BY extracted_at DESC
               LIMIT %s""",
            (company_id, limit),
        )
        rows = cur.fetchall()
        result = []
        for row in rows:
            row_dict = dict(row)
            if row_dict.get("structured_json") and isinstance(row_dict["structured_json"], str):
                try:
                    row_dict["structured_json"] = json.loads(row_dict["structured_json"])
                except json.JSONDecodeError:
                    pass
            if hasattr(row_dict.get("extracted_at"), "isoformat"):
                row_dict["extracted_at"] = row_dict["extracted_at"].isoformat()
            if hasattr(row_dict.get("confidence_score"), "__float__"):
                row_dict["confidence_score"] = float(row_dict["confidence_score"])
            result.append(row_dict)
        return result
    finally:
        db.close()


def _update_report(report_id: str, status: str, final_report: dict | None = None,
                   error: str | None = None) -> None:
    db = _get_db()
    try:
        cur = db.cursor()
        if status == "completed" and final_report:
            cur.execute(
                """UPDATE reports_researchreport
                   SET status = %s,
                       summary = %s,
                       opportunities = %s,
                       risks = %s,
                       predictions = %s,
                       confidence_score = %s,
                       completed_at = %s
                   WHERE id = %s""",
                (
                    status,
                    final_report.get("summary", ""),
                    json.dumps(final_report.get("opportunities", [])),
                    json.dumps(final_report.get("risks", [])),
                    json.dumps(final_report.get("predictions", [])),
                    final_report.get("confidence_score"),
                    datetime.now(timezone.utc),
                    report_id,
                ),
            )
            db.commit()  # Commit report update immediately
            # Insert report sections (best-effort, separate commit)
            full_text = final_report.get("full_text", "")
            if full_text:
                sections = _parse_report_sections(full_text, report_id)
                for section in sections:
                    try:
                        cur.execute(
                            """INSERT INTO reports_reportsection (report_id, section_type, content, sort_order)
                               VALUES (%s, %s, %s, %s)
                               ON DUPLICATE KEY UPDATE content = VALUES(content)""",
                            (section["report_id"], section["section_type"],
                             section["content"], section["sort_order"]),
                        )
                        db.commit()
                    except Exception as sec_err:
                        logger.warning("Section insert skipped: %s", sec_err)
                        db.rollback()
            return  # already committed above
        elif status == "failed":
            cur.execute(
                "UPDATE reports_researchreport SET status = %s, error_message = %s WHERE id = %s",
                (status, error or "Unknown error", report_id),
            )
        else:
            cur.execute(
                "UPDATE reports_researchreport SET status = %s WHERE id = %s",
                (status, report_id),
            )
        db.commit()
    finally:
        db.close()


def _parse_report_sections(full_text: str, report_id: str) -> list[dict]:
    """Extract sections from the markdown report."""
    import re
    section_map = {
        "executive summary": "executive_summary",
        "key findings": "key_findings",
        "opportunities": "opportunities",
        "risks": "risks",
        "threats": "risks",
        "predictions": "predictions",
        "methodology": "methodology",
    }
    sections = []
    order = 0
    pattern = r"##\s*(.+?)\s*\n(.*?)(?=\n##|\Z)"
    for match in re.finditer(pattern, full_text, re.DOTALL | re.IGNORECASE):
        title = match.group(1).strip().lower()
        content = match.group(2).strip()
        section_type = section_map.get(title, "key_findings")
        sections.append({
            "report_id": report_id,
            "section_type": section_type,
            "content": content,
            "sort_order": order,
        })
        order += 1
    return sections


def _publish_redis_event(report_id: str, event_type: str, payload: dict) -> None:
    """Publish a progress event to Redis pub/sub for WebSocket streaming."""
    import redis as redis_lib
    try:
        r = redis_lib.Redis.from_url(
            os.environ.get("REDIS_URL", "redis://redis:6379/0"),
            decode_responses=True,
        )
        r.publish(
            f"report:{report_id}",
            json.dumps({"type": event_type, "report_id": report_id, **payload}),
        )
    except Exception as exc:
        logger.warning("Redis publish failed: %s", exc)


@app.task(bind=True, max_retries=1, default_retry_delay=30)
def run_agent_analysis(
    self,
    company_id: int,
    report_id: str,
    max_iterations: int = 3,
    model_name: str = "moonshot-v1-8k",
):
    """
    Main Celery task: run the LangGraph multi-agent analysis pipeline.

    Steps:
    1. Load company and data points from MySQL
    2. Build initial ResearchState
    3. Run graph.invoke(state)
    4. Save final_report to MySQL ResearchReport + ReportSection rows
    5. Publish completion event to Redis pub/sub (for WebSocket)
    """
    logger.info("Starting agent analysis: report=%s company=%s", report_id, company_id)

    try:
        # ── 1. Load data ──────────────────────────────────────────────────
        company = _get_company(company_id)
        if not company:
            raise ValueError(f"Company {company_id} not found")

        data_points = _get_data_points(company_id)
        logger.info("Loaded %d data points for %s", len(data_points), company["name"])

        _publish_redis_event(report_id, "report.started", {
            "company": company["name"],
            "data_points": len(data_points),
        })

        # ── 2. Build initial state ────────────────────────────────────────
        initial_state = {
            "company_id": str(company_id),
            "company_name": company["name"],
            "raw_data_points": data_points,
            "research_notes": [],
            "analysis": {},
            "draft_report": "",
            "critique": [],
            "final_report": {},
            "iteration": 0,
            "max_iterations": max_iterations,
            "confidence_score": 0.0,
            "model_name": model_name,
            "messages": [],
        }

        # ── 3. Run LangGraph pipeline ─────────────────────────────────────
        _update_report(report_id, "running")
        _publish_redis_event(report_id, "report.running", {"message": "Pipeline started"})

        from agent.graph import get_graph
        graph = get_graph()

        # Stream events for real-time WebSocket updates
        final_state = None
        for event in graph.stream(initial_state, stream_mode="values"):
            final_state = event
            # Publish progress event based on which node just ran
            if event.get("research_notes") and not event.get("analysis"):
                _publish_redis_event(report_id, "report.progress", {
                    "stage": "researching",
                    "notes_count": len(event.get("research_notes", [])),
                })
            elif event.get("analysis") and not event.get("draft_report"):
                _publish_redis_event(report_id, "report.progress", {
                    "stage": "analysing",
                    "confidence": event.get("analysis", {}).get("confidence", 0),
                })
            elif event.get("draft_report") and not event.get("critique"):
                _publish_redis_event(report_id, "report.progress", {
                    "stage": "writing",
                    "draft_length": len(event.get("draft_report", "")),
                })
            elif event.get("critique") is not None:
                _publish_redis_event(report_id, "report.progress", {
                    "stage": "reviewing",
                    "confidence": event.get("confidence_score", 0),
                    "issues": len(event.get("critique", [])),
                })

        if not final_state:
            raise RuntimeError("LangGraph pipeline returned no state")

        # ── 4. Save results ───────────────────────────────────────────────
        final_report = final_state.get("final_report", {})
        if not final_report:
            # Use draft if critic didn't produce final_report
            analysis = final_state.get("analysis", {})
            final_report = {
                "summary": final_state.get("draft_report", "")[:1000],
                "full_text": final_state.get("draft_report", ""),
                "opportunities": analysis.get("opportunities", []),
                "risks": analysis.get("risks", []),
                "predictions": [],
                "confidence_score": final_state.get("confidence_score", 0.5),
                "iterations": final_state.get("iteration", 1),
            }

        _update_report(report_id, "completed", final_report=final_report)
        logger.info(
            "Agent analysis complete: report=%s confidence=%.2f",
            report_id, final_report.get("confidence_score", 0),
        )

        # ── 5. Publish completion ─────────────────────────────────────────
        _publish_redis_event(report_id, "report.completed", {
            "confidence_score": final_report.get("confidence_score"),
            "iterations": final_report.get("iterations"),
        })

        return {
            "status": "completed",
            "report_id": report_id,
            "confidence_score": final_report.get("confidence_score"),
        }

    except Exception as exc:
        logger.error("Agent analysis failed: report=%s error=%s", report_id, exc, exc_info=True)
        _update_report(report_id, "failed", error=str(exc))
        _publish_redis_event(report_id, "report.failed", {"error": str(exc)})
        raise self.retry(exc=exc)
