"""
LogPulse — Central Configuration
Loads all settings from environment / .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # LLM
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL", "sqlite+aiosqlite:///./logpulse.db"
    )

    # Ingestion
    log_source: str = os.getenv("LOG_SOURCE", "simulator")
    log_file_path: str = os.getenv("LOG_FILE_PATH", "/var/log/app.log")
    simulator_interval_ms: int = int(os.getenv("SIMULATOR_INTERVAL_MS", "500"))
    simulator_spike_probability: float = float(
        os.getenv("SIMULATOR_SPIKE_PROBABILITY", "0.05")
    )

    # Anomaly Detection
    zscore_window_size: int = int(os.getenv("ZSCORE_WINDOW_SIZE", "60"))
    zscore_threshold: float = float(os.getenv("ZSCORE_THRESHOLD", "2.5"))
    error_rate_threshold: float = float(os.getenv("ERROR_RATE_THRESHOLD", "0.3"))
    llm_enrichment_timeout_seconds: float = float(
        os.getenv("LLM_ENRICHMENT_TIMEOUT_SECONDS", "30")
    )

    # Alerting
    webhook_receiver_url: str = os.getenv(
        "WEBHOOK_RECEIVER_URL", "http://localhost:8000/webhook/receiver"
    )

    # Dashboard
    dashboard_title: str = os.getenv(
        "DASHBOARD_TITLE", "LogPulse — Intelligent Observability"
    )


settings = Settings()
