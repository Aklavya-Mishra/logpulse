"""
LogPulse — Log Simulator
Generates realistic synthetic application logs with configurable
spike probability to trigger anomaly detection.
"""

import asyncio
import random
import string
from datetime import datetime, timezone
from typing import AsyncGenerator

from config import settings

SERVICES = [
    "auth-service",
    "payment-service",
    "user-service",
    "notification-service",
    "api-gateway",
]

INFO_MESSAGES = [
    "Request processed successfully",
    "User session created",
    "Cache hit for key {key}",
    "Database query completed in {ms}ms",
    "Health check passed",
    "Token validated for user {user}",
    "Response sent with status 200",
    "Config reloaded",
    "Queue depth: {n} messages",
    "Connection pool size: {n}",
]

WARN_MESSAGES = [
    "Response time degraded: {ms}ms",
    "Retry attempt {n} for downstream call",
    "Memory usage at {pct}%",
    "Rate limit approaching for client {ip}",
    "Deprecated endpoint called",
    "Cache miss — falling back to DB",
    "Queue depth elevated: {n} messages",
]

ERROR_MESSAGES = [
    "Database connection timeout after {ms}ms",
    "Upstream service unavailable: {svc}",
    "Failed to parse request body: invalid JSON",
    "Authentication token expired for user {user}",
    "Unhandled exception in request handler",
    "Circuit breaker OPEN for {svc}",
    "Payment processing failed: gateway error",
    "Null pointer exception in OrderController",
    "Redis connection refused",
    "HTTP 500 returned to client {ip}",
]

CRITICAL_MESSAGES = [
    "FATAL: Database cluster unreachable",
    "Out of memory — JVM heap exhausted",
    "Cascading failure detected across {n} services",
    "Data corruption detected in shard {n}",
    "Security alert: brute force detected from {ip}",
]


def _fill(template: str) -> str:
    """Fill template placeholders with random values."""
    return (
        template
        .replace("{key}", "".join(random.choices(string.ascii_lowercase, k=8)))
        .replace("{ms}", str(random.randint(10, 3000)))
        .replace("{user}", f"user_{random.randint(1000, 9999)}")
        .replace("{n}", str(random.randint(1, 100)))
        .replace("{pct}", str(random.randint(60, 95)))
        .replace("{ip}", f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}")
        .replace("{svc}", random.choice(SERVICES))
    )


def _pick_level(spike: bool) -> tuple[str, str]:
    """
    Pick a log level and message.
    During a spike, heavily weight ERROR/CRITICAL.
    """
    if spike:
        level = random.choices(
            ["ERROR", "CRITICAL", "WARN"],
            weights=[0.65, 0.20, 0.15],
        )[0]
    else:
        level = random.choices(
            ["INFO", "WARN", "ERROR", "CRITICAL"],
            weights=[0.75, 0.15, 0.09, 0.01],
        )[0]

    if level == "INFO":
        msg = _fill(random.choice(INFO_MESSAGES))
    elif level == "WARN":
        msg = _fill(random.choice(WARN_MESSAGES))
    elif level == "ERROR":
        msg = _fill(random.choice(ERROR_MESSAGES))
    else:
        msg = _fill(random.choice(CRITICAL_MESSAGES))

    return level, msg


async def simulate_logs() -> AsyncGenerator[dict, None]:
    """
    Async generator that yields one synthetic log entry per interval.
    Occasionally enters a 'spike' window to simulate an incident.
    """
    spike_active = False
    spike_remaining = 0
    interval = settings.simulator_interval_ms / 1000.0

    while True:
        # Decide if a spike starts this tick
        if not spike_active and random.random() < settings.simulator_spike_probability:
            spike_active = True
            spike_remaining = random.randint(10, 30)  # spike lasts 10-30 log entries

        if spike_active:
            spike_remaining -= 1
            if spike_remaining <= 0:
                spike_active = False

        service = random.choice(SERVICES)
        level, message = _pick_level(spike=spike_active)
        timestamp = datetime.now(timezone.utc)

        raw = f"{timestamp.isoformat()} [{level}] {service} — {message}"

        yield {
            "timestamp": timestamp,
            "level": level,
            "service": service,
            "message": message,
            "raw": raw,
            "spike": spike_active,
        }

        await asyncio.sleep(interval)
