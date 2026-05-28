"""
LogPulse — Database CRUD Operations
All read/write operations for logs and anomalies.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import LogEntry, Anomaly


async def insert_log(session: AsyncSession, level: str, service: str, message: str, raw: str) -> LogEntry:
    """Insert a single log entry."""
    entry = LogEntry(
        timestamp=datetime.now(timezone.utc),
        level=level,
        service=service,
        message=message,
        raw=raw,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def insert_anomaly(
    session: AsyncSession,
    service: str,
    error_rate: float,
    zscore: float,
    window_size: int,
    error_count: int,
    total_count: int,
    llm_root_cause: Optional[str] = None,
    llm_severity: Optional[str] = None,
    llm_suggested_action: Optional[str] = None,
    llm_provider_used: Optional[str] = None,
    webhook_fired: bool = False,
    webhook_status: Optional[str] = None,
) -> Anomaly:
    """Insert a detected anomaly record."""
    anomaly = Anomaly(
        detected_at=datetime.now(timezone.utc),
        service=service,
        error_rate=error_rate,
        zscore=zscore,
        window_size=window_size,
        error_count=error_count,
        total_count=total_count,
        llm_root_cause=llm_root_cause,
        llm_severity=llm_severity,
        llm_suggested_action=llm_suggested_action,
        llm_provider_used=llm_provider_used,
        webhook_fired=webhook_fired,
        webhook_status=webhook_status,
    )
    session.add(anomaly)
    await session.commit()
    await session.refresh(anomaly)
    return anomaly


async def get_recent_logs(session: AsyncSession, limit: int = 100) -> List[LogEntry]:
    """Fetch the most recent log entries."""
    result = await session.execute(
        select(LogEntry).order_by(desc(LogEntry.timestamp)).limit(limit)
    )
    return result.scalars().all()


async def get_recent_anomalies(session: AsyncSession, limit: int = 20) -> List[Anomaly]:
    """Fetch the most recent anomalies."""
    result = await session.execute(
        select(Anomaly).order_by(desc(Anomaly.detected_at)).limit(limit)
    )
    return result.scalars().all()


async def get_error_rate_timeseries(
    session: AsyncSession, minutes: int = 30
) -> List[dict]:
    """
    Returns per-minute error rate for the last N minutes.
    Used by the dashboard health trend chart.
    """
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    result = await session.execute(
        select(LogEntry).where(LogEntry.timestamp >= since).order_by(LogEntry.timestamp)
    )
    logs = result.scalars().all()

    # Bucket by minute
    buckets: dict = {}
    for log in logs:
        minute_key = log.timestamp.strftime("%H:%M")
        if minute_key not in buckets:
            buckets[minute_key] = {"total": 0, "errors": 0}
        buckets[minute_key]["total"] += 1
        if log.level in ("ERROR", "CRITICAL"):
            buckets[minute_key]["errors"] += 1

    return [
        {
            "time": k,
            "error_rate": round(v["errors"] / v["total"], 3) if v["total"] > 0 else 0,
            "total": v["total"],
            "errors": v["errors"],
        }
        for k, v in sorted(buckets.items())
    ]


async def get_log_stats(session: AsyncSession) -> dict:
    """Returns aggregate counts by log level."""
    result = await session.execute(
        select(LogEntry.level, func.count(LogEntry.id)).group_by(LogEntry.level)
    )
    rows = result.all()
    stats = {"INFO": 0, "WARN": 0, "ERROR": 0, "CRITICAL": 0, "total": 0}
    for level, count in rows:
        stats[level] = count
        stats["total"] += count
    return stats
