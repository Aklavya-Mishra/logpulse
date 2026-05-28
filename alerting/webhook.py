"""
LogPulse — Webhook Alerting
Fires anomaly alerts to the configured webhook receiver.
In MVP: self-contained simulated receiver at /webhook/receiver.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from config import settings
from detection.detector import AnomalyResult
from llm.enrichment import LLMEnrichment

logger = logging.getLogger(__name__)


def build_alert_payload(
    anomaly: AnomalyResult,
    enrichment: LLMEnrichment,
) -> dict:
    """Construct the webhook alert payload."""
    return {
        "event": "anomaly_detected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": anomaly.service,
        "metrics": {
            "error_rate": anomaly.error_rate,
            "zscore": anomaly.zscore,
            "error_count": anomaly.error_count,
            "total_count": anomaly.total_count,
            "window_size": anomaly.window_size,
        },
        "analysis": {
            "severity": enrichment.severity,
            "root_cause": enrichment.root_cause,
            "suggested_action": enrichment.suggested_action,
            "llm_provider": enrichment.provider_used,
        },
        "source": "logpulse",
    }


async def fire_webhook(
    anomaly: AnomalyResult,
    enrichment: LLMEnrichment,
) -> tuple[bool, str]:
    """
    Fire anomaly alert to webhook receiver.

    Returns:
        (success: bool, status: str)
    """
    payload = build_alert_payload(anomaly, enrichment)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                settings.webhook_receiver_url,
                json=payload,
            )
            response.raise_for_status()
            logger.info(
                f"Webhook fired for {anomaly.service} — "
                f"severity={enrichment.severity} status={response.status_code}"
            )
            return True, "success"
    except Exception as e:
        logger.error(f"Webhook delivery failed: {e}")
        return False, "failed"
