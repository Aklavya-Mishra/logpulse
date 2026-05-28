"""
LogPulse — LLM Enrichment Layer
Semantic anomaly enrichment via Ollama (primary) or OpenAI (fallback).
Called only when the statistical gate fires — never on every log entry.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from config import settings
from detection.detector import AnomalyResult

logger = logging.getLogger(__name__)

ENRICHMENT_PROMPT = """You are an expert Site Reliability Engineer analyzing a log anomaly.

Anomaly details:
- Service: {service}
- Error rate in window: {error_rate:.1%}
- Z-score deviation: {zscore:.2f} (threshold: {threshold})
- Errors in window: {error_count} out of {total_count} log entries

Based on this anomaly pattern, provide a concise analysis in JSON format only.
Respond with ONLY valid JSON, no markdown, no explanation outside the JSON.

{{
  "root_cause": "Most likely root cause in 1-2 sentences",
  "severity": "LOW|MEDIUM|HIGH|CRITICAL",
  "suggested_action": "Immediate action for an SRE in 1-2 sentences"
}}"""


@dataclass
class LLMEnrichment:
    """Structured LLM enrichment output."""
    root_cause: str
    severity: str
    suggested_action: str
    provider_used: str


def _build_prompt(anomaly: AnomalyResult) -> str:
    return ENRICHMENT_PROMPT.format(
        service=anomaly.service,
        error_rate=anomaly.error_rate,
        zscore=anomaly.zscore,
        threshold=settings.zscore_threshold,
        error_count=anomaly.error_count,
        total_count=anomaly.total_count,
    )


def _parse_llm_response(text: str, provider: str) -> LLMEnrichment:
    """Parse JSON response from LLM, with fallback on parse failure."""
    try:
        # Strip any accidental markdown fences
        clean = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(clean)
        return LLMEnrichment(
            root_cause=data.get("root_cause", "Unable to determine root cause."),
            severity=data.get("severity", "MEDIUM"),
            suggested_action=data.get("suggested_action", "Investigate service logs."),
            provider_used=provider,
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"LLM response parse failed: {e}. Raw: {text[:200]}")
        return LLMEnrichment(
            root_cause="LLM response could not be parsed.",
            severity="MEDIUM",
            suggested_action="Manually inspect service logs for the anomaly window.",
            provider_used=provider,
        )


async def _enrich_via_ollama(prompt: str) -> Optional[LLMEnrichment]:
    """Call local Ollama instance for enrichment."""
    url = f"{settings.ollama_base_url}/api/generate"
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            raw_text = data.get("response", "")
            return _parse_llm_response(raw_text, provider="ollama")
    except Exception as e:
        logger.warning(f"Ollama enrichment failed: {e}")
        return None


async def _enrich_via_openai(prompt: str) -> Optional[LLMEnrichment]:
    """Call OpenAI API for enrichment (fallback)."""
    if not settings.openai_api_key:
        logger.warning("OpenAI fallback triggered but OPENAI_API_KEY is not set.")
        return None

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.openai_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            raw_text = data["choices"][0]["message"]["content"]
            return _parse_llm_response(raw_text, provider="openai")
    except Exception as e:
        logger.warning(f"OpenAI enrichment failed: {e}")
        return None


async def enrich_anomaly(anomaly: AnomalyResult) -> LLMEnrichment:
    """
    Enrich a detected anomaly with LLM semantic analysis.
    Tries Ollama first; falls back to OpenAI if Ollama is unavailable.
    Returns a safe default if both fail.
    """
    prompt = _build_prompt(anomaly)

    if settings.llm_provider == "ollama":
        result = await _enrich_via_ollama(prompt)
        if result:
            return result
        logger.warning("Ollama unavailable — attempting OpenAI fallback.")
        result = await _enrich_via_openai(prompt)
        if result:
            return result
    else:
        result = await _enrich_via_openai(prompt)
        if result:
            return result

    # Both failed — return safe default
    return LLMEnrichment(
        root_cause="LLM enrichment unavailable. Check Ollama or OpenAI configuration.",
        severity="MEDIUM",
        suggested_action="Manually inspect service logs for the anomaly window.",
        provider_used="none",
    )
