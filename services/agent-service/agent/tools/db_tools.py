"""
Database tools for the agent to query collected scraper data.
"""
import json
import logging
import os
from typing import Optional

import MySQLdb
from langchain_core.tools import tool

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


@tool
def query_collected_data(company_id: str, source_type: Optional[str] = None) -> list[dict]:
    """
    Query scraped data points from the MySQL database for a given company.

    Args:
        company_id: The numeric company ID as a string.
        source_type: Optional filter. One of: news, jobs, crunchbase, linkedin, custom.

    Returns:
        List of data points with keys: id, source_type, source_url, raw_text,
        structured_json, extracted_at, confidence_score.
    """
    db = _get_db()
    try:
        cur = db.cursor(MySQLdb.cursors.DictCursor)
        if source_type:
            cur.execute(
                """SELECT id, source_type, source_url, raw_text, structured_json,
                          extracted_at, confidence_score
                   FROM companies_datapoint
                   WHERE company_id = %s AND source_type = %s
                   ORDER BY extracted_at DESC
                   LIMIT 50""",
                (int(company_id), source_type),
            )
        else:
            cur.execute(
                """SELECT id, source_type, source_url, raw_text, structured_json,
                          extracted_at, confidence_score
                   FROM companies_datapoint
                   WHERE company_id = %s
                   ORDER BY extracted_at DESC
                   LIMIT 100""",
                (int(company_id),),
            )

        rows = cur.fetchall()
        results = []
        for row in rows:
            row_dict = dict(row)
            # Deserialise JSON blob
            if row_dict.get("structured_json") and isinstance(row_dict["structured_json"], str):
                try:
                    row_dict["structured_json"] = json.loads(row_dict["structured_json"])
                except json.JSONDecodeError:
                    pass
            # Convert datetime to string
            if hasattr(row_dict.get("extracted_at"), "isoformat"):
                row_dict["extracted_at"] = row_dict["extracted_at"].isoformat()
            if hasattr(row_dict.get("confidence_score"), "__float__"):
                row_dict["confidence_score"] = float(row_dict["confidence_score"])
            results.append(row_dict)

        logger.info(
            "query_collected_data(company=%s, source=%s) → %d rows",
            company_id, source_type, len(results),
        )
        return results

    except Exception as exc:
        logger.error("query_collected_data error: %s", exc)
        return [{"error": str(exc)}]
    finally:
        db.close()
