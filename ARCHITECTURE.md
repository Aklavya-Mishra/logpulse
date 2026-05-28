# LogPulse — Architecture Document

> **Intelligent Observability & Event Watchdog**
> Python · FastAPI · Ollama · SQLite · Docker

---

## System Overview

LogPulse is a real-time log observability platform that combines statistical anomaly detection with local LLM semantic enrichment. The system ingests application logs, applies a sliding-window Z-score gate to detect error spikes, and escalates confirmed anomalies to a local LLM for root cause analysis — all without leaving your infrastructure.

---

## High-Level Architecture

```mermaid
graph TB
    subgraph Ingestion
        SIM[Log Simulator] -->|async generator| PIPE[Ingestion Pipeline]
        FILE[Log File Tailer] -->|parsed raw lines| PIPE
        APIIN[POST /api/logs] -->|raw or structured logs| PIPE
    end

    subgraph Detection
        PIPE -->|log event| STAT[Statistical Gate<br/>Z-score + Sliding Window]
        STAT -->|anomaly detected| LLM[LLM Enrichment<br/>Ollama llama3.1:8b]
        STAT -->|no anomaly| DB_LOG[(logs table)]
    end

    subgraph Alerting
        LLM -->|enriched anomaly| HOOK[Webhook Alerting]
        HOOK -->|POST| RECV[/webhook/receiver]
    end

    subgraph Persistence
        LLM --> DB_ANO[(anomalies table)]
        PIPE --> DB_LOG
    end

    subgraph Dashboard
        DB_LOG --> SSE[SSE Broadcast]
        DB_ANO --> SSE
        SSE -->|EventSource| BROWSER[Browser Dashboard<br/>Chart.js + Jinja2]
    end
```

---

## Data Flow

```mermaid
sequenceDiagram
    participant SRC as Log Source
    participant PIPE as Ingestion Pipeline
    participant STAT as Statistical Detector
    participant LLM as LLM Enrichment
    participant HOOK as Webhook
    participant DB as SQLite DB
    participant SSE as SSE Stream
    participant UI as Dashboard

    SRC->>PIPE: simulator, file, or API log entry
    PIPE->>DB: INSERT into logs
    PIPE->>SSE: broadcast log event
    PIPE->>STAT: ingest(service, level)

    alt No anomaly
        STAT-->>PIPE: None
    else Anomaly detected
        STAT->>LLM: AnomalyResult (error_rate, zscore)
        LLM->>LLM: build_prompt()
        LLM->>LLM: call Ollama /api/generate
        LLM-->>STAT: LLMEnrichment (root_cause, severity, action)
        STAT->>HOOK: fire_webhook(anomaly, enrichment)
        HOOK->>HOOK: POST /webhook/receiver
        STAT->>DB: INSERT into anomalies
        STAT->>SSE: broadcast anomaly event
    end

    SSE-->>UI: EventSource push
    UI->>UI: update charts + feeds
```

---

## Anomaly Detection Algorithm

```mermaid
flowchart TD
    A[New Log Entry] --> B[Push to sliding window<br/>default: 60 entries]
    B --> C[Calculate current error rate<br/>errors / window_size]
    C --> D[Push rate to history buffer<br/>max 200 points]
    D --> E{History >= 10 points?}
    E -- No --> F[Return None<br/>insufficient history]
    E -- Yes --> G[Calculate Z-score<br/>z = rate - mean / std]
    G --> H{error_rate >= 0.3<br/>AND zscore >= 2.5?}
    H -- No --> I[Return None<br/>normal traffic]
    H -- Yes --> J[Return AnomalyResult]
    J --> K[Escalate to LLM enrichment]
```

---

## Module Responsibilities

| Module | Responsibility |
|---|---|
| `ingestion/simulator.py` | Generates synthetic log stream with configurable spike probability |
| `ingestion/parser.py` | Normalizes JSON, raw text, and structured API log payloads |
| `ingestion/pipeline.py` | Orchestrates simulator and file log sources, calls `on_log` handler |
| `detection/detector.py` | Stateful sliding-window Z-score anomaly detector, one instance per app lifetime |
| `llm/enrichment.py` | Ollama/OpenAI LLM calls, prompt construction, JSON response parsing |
| `alerting/webhook.py` | Builds alert payload, fires to webhook receiver |
| `db/models.py` | SQLAlchemy async models: `LogEntry`, `Anomaly` |
| `db/crud.py` | All DB read/write operations |
| `api/app.py` | FastAPI app, API log ingestion, SSE broadcast, route handlers, pipeline orchestration |
| `dashboard/templates/` | Jinja2 HTML template, Chart.js, SSE client |
| `config.py` | Central settings loaded from `.env` |

---

## Database Schema

```mermaid
erDiagram
    logs {
        int id PK
        datetime timestamp
        string level
        string service
        text message
        text raw
    }

    anomalies {
        int id PK
        datetime detected_at
        string service
        float error_rate
        float zscore
        int window_size
        int error_count
        int total_count
        text llm_root_cause
        string llm_severity
        text llm_suggested_action
        string llm_provider_used
        bool webhook_fired
        string webhook_status
    }
```

---

## LLM Provider Strategy

LLM enrichment is bounded by `LLM_ENRICHMENT_TIMEOUT_SECONDS`. If enrichment
times out or all providers fail, the anomaly is still persisted with a safe
fallback analysis so detection and alerting continue.

```mermaid
flowchart LR
    A[Anomaly Detected] --> B{LLM_PROVIDER?}
    B -- ollama --> C[Call Ollama<br/>llama3.1:8b local]
    C --> D{Success?}
    D -- Yes --> G[Return LLMEnrichment]
    D -- No --> E[Call OpenAI<br/>gpt-4o-mini fallback]
    E --> F{Success?}
    F -- Yes --> G
    F -- No --> H[Return safe default<br/>provider=none]
    B -- openai --> E
```

---

## Tech Stack

| Layer | Technology | License |
|---|---|---|
| API Framework | FastAPI 0.111 | MIT |
| ASGI Server | Uvicorn | BSD |
| Templating | Jinja2 | BSD |
| SSE | sse-starlette | BSD |
| Database | SQLite + SQLAlchemy async | MIT / PSF |
| Statistical Analysis | NumPy | BSD |
| LLM (primary) | Ollama `llama3.1:8b` | MIT |
| LLM (fallback) | OpenAI `gpt-4o-mini` | Paid API |
| HTTP Client | HTTPX | BSD |
| Charts | Chart.js 4.4 | MIT |
| Containerization | Docker Engine | Apache 2.0 |
| Testing | pytest + pytest-asyncio | MIT |

---

## Deployment

Single command deployment:

```bash
docker-compose up
```

Services started:
- `logpulse` — FastAPI app on port 8000
- `ollama` — Local LLM server on port 11434

Dashboard: **http://localhost:8000**
API docs: **http://localhost:8000/docs**
