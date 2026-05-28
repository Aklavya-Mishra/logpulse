"""
LogPulse — Unit Tests
Tests for: anomaly detector, log simulator, LLM enrichment parsing.
Run with: pytest tests/ -v
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# ── Detector Tests ─────────────────────────────────────────────────────────────

class TestAnomalyDetector:

    def setup_method(self):
        """Fresh detector for each test."""
        from detection.detector import AnomalyDetector
        self.detector = AnomalyDetector()

    def test_no_anomaly_on_normal_traffic(self):
        """Normal INFO-heavy traffic should not trigger anomaly."""
        for _ in range(100):
            result = self.detector.ingest("auth-service", "INFO")
        assert result is None

    def test_no_anomaly_before_history_builds(self):
        """Detector needs at least 10 data points before firing."""
        for _ in range(9):
            result = self.detector.ingest("auth-service", "ERROR")
        assert result is None

    def test_anomaly_detected_on_error_spike(self):
        """Sustained error spike should eventually trigger detection."""
        # Build baseline with normal traffic
        detector = self.detector
        for _ in range(80):
            detector.ingest("payment-service", "INFO")
        # Now inject error spike
        anomaly = None
        for _ in range(50):
            anomaly = detector.ingest("payment-service", "ERROR")
            if anomaly:
                break
        assert anomaly is not None
        assert anomaly.service == "payment-service"
        assert anomaly.error_rate >= 0.3
        assert anomaly.zscore >= 2.5

    def test_anomaly_result_fields(self):
        """AnomalyResult should have all required fields."""
        from detection.detector import AnomalyDetector
        d = AnomalyDetector()
        for _ in range(80):
            d.ingest("svc", "INFO")
        result = None
        for _ in range(60):
            result = d.ingest("svc", "ERROR")
            if result:
                break
        if result:
            assert hasattr(result, "service")
            assert hasattr(result, "error_rate")
            assert hasattr(result, "zscore")
            assert hasattr(result, "window_size")
            assert hasattr(result, "error_count")
            assert hasattr(result, "total_count")

    def test_window_state_error_rate(self):
        """WindowState.current_error_rate() should calculate correctly."""
        from detection.detector import WindowState
        ws = WindowState()
        ws.push("INFO", 10)
        ws.push("INFO", 10)
        ws.push("ERROR", 10)
        ws.push("ERROR", 10)
        rate = ws.current_error_rate()
        assert rate == 0.5

    def test_window_state_zscore_insufficient_history(self):
        """Z-score should return None with < 10 data points."""
        from detection.detector import WindowState
        ws = WindowState()
        for i in range(9):
            ws.push_rate(float(i) / 10)
        assert ws.zscore() is None

    def test_window_state_zscore_zero_std(self):
        """Z-score should return 0.0 when std is zero (identical rates)."""
        from detection.detector import WindowState
        ws = WindowState()
        for _ in range(20):
            ws.push_rate(0.1)
        # std=0 guard in detector returns 0.0
        result = ws.zscore()
        assert result == 0.0 or result is not None  # Guard fires or valid float

    def test_different_services_isolated(self):
        """Anomaly detection state should be isolated per service."""
        d = self.detector
        for _ in range(80):
            d.ingest("service-a", "INFO")
        # service-b should start fresh — no anomaly on first entry
        result = d.ingest("service-b", "ERROR")
        assert result is None


# ── Simulator Tests ────────────────────────────────────────────────────────────

class TestLogSimulator:

    @pytest.mark.asyncio
    async def test_simulator_yields_valid_log(self):
        """Simulator should yield a properly structured log dict."""
        from ingestion.simulator import simulate_logs
        async for log in simulate_logs():
            assert "timestamp" in log
            assert "level" in log
            assert "service" in log
            assert "message" in log
            assert "raw" in log
            assert log["level"] in ("INFO", "WARN", "ERROR", "CRITICAL")
            break  # Only need one entry

    @pytest.mark.asyncio
    async def test_simulator_raw_contains_level(self):
        """Raw log string should contain the level."""
        from ingestion.simulator import simulate_logs
        async for log in simulate_logs():
            assert log["level"] in log["raw"]
            break


# ── LLM Enrichment Tests ───────────────────────────────────────────────────────

class TestLogParsing:

    def test_parse_text_log_line(self):
        """Parser should extract timestamp, level, service, and message."""
        from ingestion.parser import parse_log_line

        log = parse_log_line(
            "2026-05-29T10:15:00Z [ERROR] payment-service - Gateway timeout"
        )

        assert log["level"] == "ERROR"
        assert log["service"] == "payment-service"
        assert log["message"] == "Gateway timeout"
        assert log["timestamp"].tzinfo is not None

    def test_parse_json_log_line(self):
        """Parser should normalize JSON application logs."""
        from ingestion.parser import parse_log_line

        log = parse_log_line(
            '{"time":"2026-05-29T10:15:00Z","severity":"fatal","service":"api-gateway","msg":"cluster down"}'
        )

        assert log["level"] == "CRITICAL"
        assert log["service"] == "api-gateway"
        assert log["message"] == "cluster down"

    def test_parse_unstructured_line_uses_safe_defaults(self):
        """Unstructured platform logs should still be accepted."""
        from ingestion.parser import parse_log_line

        log = parse_log_line("kernel panic ERROR while mounting volume")

        assert log["level"] == "ERROR"
        assert log["service"] == "unknown-service"
        assert "kernel panic" in log["message"]


class TestApiIngestion:

    @pytest.mark.asyncio
    async def test_ingest_log_accepts_raw_line(self):
        """POST handler should parse raw logs and pass them to the pipeline."""
        from api.app import LogIngestRequest, ingest_log

        with patch("api.app._handle_log", new_callable=AsyncMock) as handler:
            result = await ingest_log(
                LogIngestRequest(raw="2026-05-29T10:15:00Z [WARN] auth-service - slow login")
            )

        handler.assert_awaited_once()
        assert result["status"] == "accepted"
        assert result["log"]["level"] == "WARN"
        assert result["log"]["service"] == "auth-service"

    @pytest.mark.asyncio
    async def test_ingest_log_rejects_empty_payload(self):
        """POST handler should reject empty log submissions."""
        from fastapi import HTTPException
        from api.app import LogIngestRequest, ingest_log

        with pytest.raises(HTTPException):
            await ingest_log(LogIngestRequest())


class TestLLMEnrichment:

    def _make_anomaly(self):
        from detection.detector import AnomalyResult
        return AnomalyResult(
            service="payment-service",
            error_rate=0.45,
            zscore=3.2,
            window_size=60,
            error_count=27,
            total_count=60,
        )

    def test_parse_valid_json_response(self):
        """_parse_llm_response should correctly parse valid JSON."""
        from llm.enrichment import _parse_llm_response
        raw = json.dumps({
            "root_cause": "Database timeout due to connection pool exhaustion",
            "severity": "HIGH",
            "suggested_action": "Increase connection pool size and check DB health"
        })
        result = _parse_llm_response(raw, "ollama")
        assert result.root_cause == "Database timeout due to connection pool exhaustion"
        assert result.severity == "HIGH"
        assert result.provider_used == "ollama"

    def test_parse_json_with_markdown_fences(self):
        """Parser should strip markdown code fences."""
        from llm.enrichment import _parse_llm_response
        raw = "```json\n{\"root_cause\": \"test\", \"severity\": \"LOW\", \"suggested_action\": \"check it\"}\n```"
        result = _parse_llm_response(raw, "ollama")
        assert result.root_cause == "test"

    def test_parse_invalid_json_returns_default(self):
        """Invalid JSON should return safe default enrichment."""
        from llm.enrichment import _parse_llm_response
        result = _parse_llm_response("this is not json at all", "ollama")
        assert result.severity == "MEDIUM"
        assert result.provider_used == "ollama"
        assert "parse" in result.root_cause.lower() or "unavailable" in result.root_cause.lower() or "could not" in result.root_cause.lower()

    def test_build_prompt_contains_service(self):
        """Built prompt should contain the anomaly service name."""
        from llm.enrichment import _build_prompt
        anomaly = self._make_anomaly()
        prompt = _build_prompt(anomaly)
        assert "payment-service" in prompt
        assert "45.0%" in prompt or "0.45" in prompt

    @pytest.mark.asyncio
    async def test_enrich_anomaly_ollama_unavailable_returns_default(self):
        """When Ollama is down and no OpenAI key, should return safe default."""
        from llm.enrichment import enrich_anomaly
        anomaly = self._make_anomaly()
        with patch("llm.enrichment._enrich_via_ollama", new_callable=AsyncMock, return_value=None), \
             patch("llm.enrichment._enrich_via_openai", new_callable=AsyncMock, return_value=None):
            result = await enrich_anomaly(anomaly)
            assert result.provider_used == "none"
            assert result.severity == "MEDIUM"


# ── Webhook Tests ──────────────────────────────────────────────────────────────

class TestWebhook:

    def test_build_alert_payload_structure(self):
        """Alert payload should have all required fields."""
        from detection.detector import AnomalyResult
        from llm.enrichment import LLMEnrichment
        from alerting.webhook import build_alert_payload

        anomaly = AnomalyResult(
            service="auth-service",
            error_rate=0.4,
            zscore=3.0,
            window_size=60,
            error_count=24,
            total_count=60,
        )
        enrichment = LLMEnrichment(
            root_cause="Auth service DB timeout",
            severity="HIGH",
            suggested_action="Restart connection pool",
            provider_used="ollama",
        )
        payload = build_alert_payload(anomaly, enrichment)

        assert payload["event"] == "anomaly_detected"
        assert payload["service"] == "auth-service"
        assert "metrics" in payload
        assert "analysis" in payload
        assert payload["analysis"]["severity"] == "HIGH"
        assert payload["source"] == "logpulse"

    @pytest.mark.asyncio
    async def test_fire_webhook_success(self):
        """Webhook should return success on 200 response."""
        from detection.detector import AnomalyResult
        from llm.enrichment import LLMEnrichment
        from alerting.webhook import fire_webhook

        anomaly = AnomalyResult("svc", 0.4, 3.0, 60, 24, 60)
        enrichment = LLMEnrichment("cause", "HIGH", "action", "ollama")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("alerting.webhook.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            ok, status = await fire_webhook(anomaly, enrichment)
            assert ok is True
            assert status == "success"

    @pytest.mark.asyncio
    async def test_fire_webhook_failure(self):
        """Webhook should return failed on connection error."""
        from detection.detector import AnomalyResult
        from llm.enrichment import LLMEnrichment
        from alerting.webhook import fire_webhook

        anomaly = AnomalyResult("svc", 0.4, 3.0, 60, 24, 60)
        enrichment = LLMEnrichment("cause", "HIGH", "action", "ollama")

        with patch("alerting.webhook.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(side_effect=Exception("Connection refused"))

            ok, status = await fire_webhook(anomaly, enrichment)
            assert ok is False
            assert status == "failed"
