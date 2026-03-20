"""
Analysis tools for computing trends and metrics from collected data.
"""
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def compute_trend(
    data_points: list[dict],
    metric: str = "volume",
    window_days: int = 30,
) -> dict:
    """
    Compute trend metrics over collected data points.

    Args:
        data_points: List of data point dicts (from query_collected_data).
        metric: One of 'volume' (count over time), 'source_mix' (breakdown by source),
                'keyword_frequency' (top keywords in raw_text).
        window_days: Number of days to consider (default 30).

    Returns:
        Dict with trend analysis results.
    """
    if not data_points:
        return {"error": "No data points provided", "metric": metric}

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)

    def parse_dt(val) -> datetime | None:
        if isinstance(val, datetime):
            return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
        if isinstance(val, str):
            for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
                        "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"]:
                try:
                    dt = datetime.strptime(val[:26], fmt)
                    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
        return None

    recent = [
        dp for dp in data_points
        if (ts := parse_dt(dp.get("extracted_at"))) and ts >= cutoff
    ]

    if metric == "volume":
        # Daily volume
        by_day: defaultdict[str, int] = defaultdict(int)
        for dp in recent:
            ts = parse_dt(dp.get("extracted_at"))
            if ts:
                day_key = ts.strftime("%Y-%m-%d")
                by_day[day_key] += 1

        daily_counts = dict(sorted(by_day.items()))
        values = list(daily_counts.values())
        avg = sum(values) / len(values) if values else 0
        trend = "increasing" if len(values) >= 2 and values[-1] > values[0] else "stable"

        return {
            "metric": "volume",
            "window_days": window_days,
            "total_recent": len(recent),
            "daily_counts": daily_counts,
            "average_per_day": round(avg, 2),
            "trend": trend,
        }

    elif metric == "source_mix":
        source_counts = Counter(dp.get("source_type", "unknown") for dp in recent)
        total = sum(source_counts.values()) or 1
        breakdown = {
            src: {"count": cnt, "pct": round(cnt / total * 100, 1)}
            for src, cnt in source_counts.most_common()
        }
        return {
            "metric": "source_mix",
            "window_days": window_days,
            "total_recent": len(recent),
            "breakdown": breakdown,
        }

    elif metric == "keyword_frequency":
        import re
        STOP_WORDS = {
            "the", "a", "an", "and", "or", "in", "on", "at", "to", "for",
            "of", "is", "are", "was", "were", "be", "been", "has", "have",
            "it", "its", "this", "that", "with", "from", "by", "as", "not",
        }
        word_counts: Counter = Counter()
        for dp in recent:
            text = dp.get("raw_text", "").lower()
            words = re.findall(r"\b[a-z]{4,}\b", text)
            filtered = [w for w in words if w not in STOP_WORDS]
            word_counts.update(filtered)

        top_keywords = [
            {"word": w, "count": c} for w, c in word_counts.most_common(20)
        ]
        return {
            "metric": "keyword_frequency",
            "window_days": window_days,
            "total_recent": len(recent),
            "top_keywords": top_keywords,
        }

    else:
        return {"error": f"Unknown metric: {metric}. Use: volume, source_mix, keyword_frequency"}
