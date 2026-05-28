"""
LogPulse - Log parsing helpers.
Normalizes raw application/platform log lines and API payloads.
"""

import json
import re
from datetime import datetime, timezone
from typing import Any


VALID_LEVELS = {"DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL"}
LEVEL_ALIASES = {
    "WARNING": "WARN",
    "FATAL": "CRITICAL",
}

TEXT_LOG_RE = re.compile(
    r"^(?:(?P<timestamp>\S+)\s+)?"
    r"(?:\[(?P<bracket_level>[A-Za-z]+)\]|(?P<plain_level>DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL|FATAL))"
    r"\s+"
    r"(?P<service>[A-Za-z0-9_.:/-]+)"
    r"(?:\s+(?:-|--|:)\s+|\s+)"
    r"(?P<message>.*)$",
    re.IGNORECASE,
)


def normalize_level(level: str | None) -> str:
    """Return a supported log level, defaulting to INFO for unknown values."""
    candidate = (level or "INFO").upper()
    if candidate not in VALID_LEVELS:
        return "INFO"
    return LEVEL_ALIASES.get(candidate, candidate)


def parse_timestamp(value: Any) -> datetime:
    """Parse common timestamp inputs into a timezone-aware UTC datetime."""
    if isinstance(value, datetime):
        timestamp = value
    elif isinstance(value, str) and value.strip():
        raw = value.strip()
        if raw.endswith("Z"):
            raw = f"{raw[:-1]}+00:00"
        try:
            timestamp = datetime.fromisoformat(raw)
        except ValueError:
            timestamp = datetime.now(timezone.utc)
    else:
        timestamp = datetime.now(timezone.utc)

    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def normalize_log(
    *,
    level: str | None = None,
    service: str | None = None,
    message: str | None = None,
    raw: str | None = None,
    timestamp: Any = None,
) -> dict:
    """Build the canonical log dict consumed by the pipeline."""
    normalized_level = normalize_level(level)
    normalized_service = (service or "unknown-service").strip() or "unknown-service"
    normalized_message = (message or raw or "").strip()
    parsed_timestamp = parse_timestamp(timestamp)
    normalized_raw = raw or (
        f"{parsed_timestamp.isoformat()} [{normalized_level}] "
        f"{normalized_service} - {normalized_message}"
    )

    return {
        "timestamp": parsed_timestamp,
        "level": normalized_level,
        "service": normalized_service,
        "message": normalized_message,
        "raw": normalized_raw,
    }


def parse_log_line(raw: str) -> dict:
    """
    Parse a raw log line into the canonical log shape.
    Supports JSON lines and common text log formats.
    """
    line = raw.strip()
    if not line:
        return normalize_log(raw=raw, message="")

    try:
        data = json.loads(line)
        if isinstance(data, dict):
            return normalize_log(
                level=data.get("level") or data.get("severity"),
                service=data.get("service") or data.get("logger") or data.get("app"),
                message=data.get("message") or data.get("msg") or line,
                raw=line,
                timestamp=data.get("timestamp") or data.get("time") or data.get("ts"),
            )
    except json.JSONDecodeError:
        pass

    match = TEXT_LOG_RE.match(line)
    if match:
        groups = match.groupdict()
        return normalize_log(
            level=groups.get("bracket_level") or groups.get("plain_level"),
            service=groups.get("service"),
            message=groups.get("message"),
            raw=line,
            timestamp=groups.get("timestamp"),
        )

    detected_level = next((level for level in VALID_LEVELS if re.search(rf"\b{level}\b", line, re.I)), "INFO")
    return normalize_log(
        level=detected_level,
        service="unknown-service",
        message=line,
        raw=line,
    )
