"""
LogPulse — Main FastAPI Application
Routes: dashboard, SSE stream, webhook receiver, REST API endpoints.
Orchestrates: ingestion pipeline → anomaly detector → LLM enrichment → webhook → DB.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.models import init_db, get_session
from db.crud import (
    insert_log,
    insert_anomaly,
    get_recent_logs,
    get_recent_anomalies,
    get_error_rate_timeseries,
    get_log_stats,
)
from ingestion.pipeline import run_ingestion
from ingestion.parser import normalize_log, parse_log_line
from detection.detector import detector, AnomalyResult
from llm.enrichment import LLMEnrichment, enrich_anomaly
from alerting.webhook import fire_webhook, build_alert_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
logger = logging.getLogger(__name__)


class LogIngestRequest(BaseModel):
    """Request body for API-based log ingestion."""

    raw: str | None = Field(default=None, description="Raw log line to parse")
    timestamp: datetime | None = None
    level: str | None = None
    service: str | None = None
    message: str | None = None

# ── SSE broadcast queue ────────────────────────────────────────────────────────
# All connected SSE clients receive events from this queue.
_sse_subscribers: list[asyncio.Queue] = []


async def _broadcast(event_type: str, data: dict):
    """Push an event to all connected SSE clients."""
    payload = json.dumps(data)
    dead = []
    for q in _sse_subscribers:
        try:
            q.put_nowait((event_type, payload))
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        _sse_subscribers.remove(q)


# ── Core log handler ───────────────────────────────────────────────────────────
async def _handle_log(log: dict):
    """
    Called for every ingested log entry.
    1. Persist to DB
    2. Run statistical anomaly gate
    3. If anomaly: LLM enrichment → webhook → persist anomaly
    4. Broadcast log + optional anomaly to SSE clients
    5. Periodically push timeseries update
    """
    async for session in get_session():
            # 1. Persist log
            await insert_log(
                session,
                level=log["level"],
                service=log["service"],
                message=log["message"],
                raw=log["raw"],
            )

            # 2. Broadcast log event to dashboard
            await _broadcast("log", {
                "timestamp": log["timestamp"].isoformat(),
                "level": log["level"],
                "service": log["service"],
                "message": log["message"],
            })

            # 3. Statistical gate
            anomaly_result: AnomalyResult | None = detector.ingest(
                service=log["service"],
                level=log["level"],
            )

            if anomaly_result:
                logger.warning(
                    f"ANOMALY DETECTED — service={anomaly_result.service} "
                    f"error_rate={anomaly_result.error_rate:.1%} "
                    f"zscore={anomaly_result.zscore:.2f}"
                )

                # 4. LLM enrichment
                try:
                    enrichment = await asyncio.wait_for(
                        enrich_anomaly(anomaly_result),
                        timeout=settings.llm_enrichment_timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    logger.warning("LLM enrichment timed out; using safe default.")
                    enrichment = LLMEnrichment(
                        root_cause="LLM enrichment timed out.",
                        severity="MEDIUM",
                        suggested_action="Inspect service logs and verify downstream dependencies.",
                        provider_used="timeout",
                    )

                # 5. Fire webhook
                webhook_ok, webhook_status = await fire_webhook(anomaly_result, enrichment)

                # 6. Persist anomaly
                await insert_anomaly(
                    session,
                    service=anomaly_result.service,
                    error_rate=anomaly_result.error_rate,
                    zscore=anomaly_result.zscore,
                    window_size=anomaly_result.window_size,
                    error_count=anomaly_result.error_count,
                    total_count=anomaly_result.total_count,
                    llm_root_cause=enrichment.root_cause,
                    llm_severity=enrichment.severity,
                    llm_suggested_action=enrichment.suggested_action,
                    llm_provider_used=enrichment.provider_used,
                    webhook_fired=webhook_ok,
                    webhook_status=webhook_status,
                )

                # 7. Broadcast anomaly event
                alert_payload = build_alert_payload(anomaly_result, enrichment)
                await _broadcast("anomaly", alert_payload)

            # 8. Periodically push timeseries (every 10th log)
            if _log_counter[0] % 10 == 0:
                timeseries = await get_error_rate_timeseries(session, minutes=30)
                await _broadcast("timeseries", timeseries)

            _log_counter[0] += 1


_log_counter = [0]


# ── Application lifespan ───────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB and start ingestion pipeline on startup."""
    await init_db()
    logger.info("Database initialized.")

    ingestion_task = asyncio.create_task(run_ingestion(_handle_log))
    logger.info(f"Ingestion pipeline started. Source: {settings.log_source}")

    yield

    ingestion_task.cancel()
    try:
        await ingestion_task
    except asyncio.CancelledError:
        pass
    logger.info("LogPulse shutdown complete.")


# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="LogPulse",
    description="Intelligent Observability & Event Watchdog",
    version="1.0.0",
    lifespan=lifespan,
)

templates = Jinja2Templates(directory="dashboard/templates")


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the main observability dashboard."""
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": settings.dashboard_title},
    )


@app.get("/stream")
async def stream(request: Request):
    """
    SSE endpoint — streams log, anomaly, and timeseries events to the dashboard.
    Each connected browser tab gets its own queue.
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=500)
    _sse_subscribers.append(queue)

    async def event_generator() -> AsyncGenerator:
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event_type, data = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield {"event": event_type, "data": data}
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield {"comment": "keepalive"}
        finally:
            if queue in _sse_subscribers:
                _sse_subscribers.remove(queue)

    return EventSourceResponse(event_generator())


@app.post("/webhook/receiver")
async def webhook_receiver(payload: dict):
    """
    Simulated webhook receiver endpoint.
    Logs the received alert — in production this would forward to PagerDuty/Slack.
    """
    logger.info(
        f"[WEBHOOK RECEIVED] service={payload.get('service')} "
        f"severity={payload.get('analysis', {}).get('severity')} "
        f"ts={payload.get('timestamp')}"
    )
    return {"status": "received", "timestamp": datetime.now(timezone.utc).isoformat()}


# ── REST API ───────────────────────────────────────────────────────────────────

@app.post("/api/logs", status_code=status.HTTP_202_ACCEPTED)
async def ingest_log(payload: LogIngestRequest):
    """Accept one application/platform log entry and feed it through detection."""
    if payload.raw:
        log = parse_log_line(payload.raw)
    elif payload.level or payload.service or payload.message:
        log = normalize_log(
            level=payload.level,
            service=payload.service,
            message=payload.message,
            timestamp=payload.timestamp,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either raw or at least one structured log field.",
        )

    await _handle_log(log)
    return {
        "status": "accepted",
        "log": {
            "timestamp": log["timestamp"].isoformat(),
            "level": log["level"],
            "service": log["service"],
            "message": log["message"],
        },
    }


@app.get("/api/logs")
async def get_logs(limit: int = 100, session: AsyncSession = Depends(get_session)):
    """Return recent log entries."""
    logs = await get_recent_logs(session, limit=limit)
    return [
        {
            "id": l.id,
            "timestamp": l.timestamp.isoformat(),
            "level": l.level,
            "service": l.service,
            "message": l.message,
        }
        for l in logs
    ]


@app.get("/api/anomalies")
async def get_anomalies(limit: int = 20, session: AsyncSession = Depends(get_session)):
    """Return recent anomaly records with LLM enrichment."""
    anomalies = await get_recent_anomalies(session, limit=limit)
    return [
        {
            "id": a.id,
            "detected_at": a.detected_at.isoformat(),
            "service": a.service,
            "error_rate": a.error_rate,
            "zscore": a.zscore,
            "error_count": a.error_count,
            "total_count": a.total_count,
            "severity": a.llm_severity,
            "root_cause": a.llm_root_cause,
            "suggested_action": a.llm_suggested_action,
            "llm_provider": a.llm_provider_used,
            "webhook_fired": a.webhook_fired,
            "webhook_status": a.webhook_status,
        }
        for a in anomalies
    ]


@app.get("/api/stats")
async def get_stats(session: AsyncSession = Depends(get_session)):
    """Return aggregate log level counts."""
    return await get_log_stats(session)


@app.get("/api/timeseries")
async def get_timeseries(minutes: int = 30, session: AsyncSession = Depends(get_session)):
    """Return per-minute error rate timeseries for the last N minutes."""
    return await get_error_rate_timeseries(session, minutes=minutes)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "logpulse", "timestamp": datetime.now(timezone.utc).isoformat()}
