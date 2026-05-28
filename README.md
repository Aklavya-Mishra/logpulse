# ⚡ LogPulse — Intelligent Observability & Event Watchdog

> Real-time log anomaly detection powered by statistical analysis and local LLM enrichment.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![OSS](https://img.shields.io/badge/100%25-Open%20Source-brightgreen.svg)]()

LogPulse ingests application logs in real-time, applies a **statistical Z-score gate** to detect error spikes, and escalates detected anomalies to a **local LLM (Ollama llama3.1:8b)** for semantic root cause analysis and remediation suggestions. Everything ships in a single `docker-compose up`.

---

## Features

- **Real-time log ingestion** — simulated log generator, file tailing, and API-submitted logs
- **Hybrid anomaly detection** — sliding window Z-score gate, LLM enrichment only on anomaly escalation
- **LLM semantic analysis** — root cause hypothesis, severity classification, suggested action via Ollama (OpenAI fallback)
- **Live dashboard** — SSE-powered, zero JS build step, Chart.js health trend visualization
- **Simulated webhook alerting** — self-contained receiver, zero external dependency
- **REST API** — `/api/logs`, `/api/anomalies`, `/api/stats`, `/api/timeseries`
- **Fully containerized** — single `docker-compose up` to run everything
- **100% open source** — MIT licensed, zero paid dependencies required

---

## Quick Start

### Prerequisites
- Docker Engine
- (Optional) Ollama installed locally for non-Docker runs

### Run with Docker (recommended)

```bash
git clone https://github.com/YOUR_USERNAME/logpulse.git
cd logpulse

# Pull and start Ollama model (first time only)
docker-compose up ollama -d
docker exec -it logpulse-ollama-1 ollama pull llama3.1:8b

# Start everything
docker-compose up
```

Open **http://localhost:8000** for the live dashboard.

To inspect the SQLite database from the running container, open Docker Desktop,
select `logpulse-1`, open the **Exec** tab, and run:

```bash
sqlite3 /app/data/logpulse.db
```

Useful SQLite commands:

```sql
.tables
SELECT * FROM logs ORDER BY id DESC LIMIT 20;
SELECT * FROM anomalies ORDER BY id DESC LIMIT 20;
```

### Run locally

```bash
git clone https://github.com/YOUR_USERNAME/logpulse.git
cd logpulse

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env as needed

# Ensure Ollama is running: ollama serve
python main.py
```

### Ingest sample logs

With the app running, open the dashboard at **http://localhost:8000** and post
the included sample CSV into the ingestion API from another terminal:

```powershell
Import-Csv .\test-logs.csv | ForEach-Object {
  Invoke-RestMethod `
    -Method Post `
    -Uri http://localhost:8000/api/logs `
    -ContentType "application/json" `
    -Body (@{ raw = $_.raw } | ConvertTo-Json)
}
```

The file includes normal traffic plus a payment-service error spike, so the
live feed, health trend, and anomaly panel should update as rows are ingested.

---

## Configuration

Runtime config is loaded from environment variables. For local runs, edit the
included `.env`; Docker Compose sets the main container values in
`docker-compose.yml`.

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama` or `openai` |
| `OLLAMA_MODEL` | `llama3.1:8b` | Any Ollama model |
| `OPENAI_API_KEY` | — | Required only if using OpenAI fallback |
| `LOG_SOURCE` | `simulator` | `simulator` or `file` |
| `LOG_FILE_PATH` | `/var/log/app.log` | File to tail when `LOG_SOURCE=file` |
| `SIMULATOR_SPIKE_PROBABILITY` | `0.05` | 0.0–1.0, controls spike frequency |
| `ZSCORE_THRESHOLD` | `2.5` | Sensitivity of anomaly detection |
| `ERROR_RATE_THRESHOLD` | `0.3` | Min error rate to trigger gate |
| `LLM_ENRICHMENT_TIMEOUT_SECONDS` | `30` | Max time to wait for LLM analysis before using a safe fallback |

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for full system design and data flow diagrams.

For reviewer-oriented context, including why anomaly detection uses a hybrid
statistical + LLM approach, see [FAQ.md](FAQ.md).

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Live observability dashboard |
| `/stream` | GET | SSE event stream (log, anomaly, timeseries) |
| `/webhook/receiver` | POST | Simulated webhook receiver |
| `/api/logs` | POST | Ingest one raw or structured log entry |
| `/api/logs` | GET | Recent log entries |
| `/api/anomalies` | GET | Recent anomalies with LLM enrichment |
| `/api/stats` | GET | Log level aggregate counts |
| `/api/timeseries` | GET | Per-minute error rate timeseries |
| `/health` | GET | Health check |

Example `POST /api/logs` payload:

```json
{
  "raw": "2026-05-29T10:15:00Z [ERROR] payment-service - Gateway timeout"
}
```

---

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

---

## Repository Hygiene

Use `.env.example` as the committed configuration template. Keep local secrets
and runtime artifacts out of git; `.gitignore` excludes `.env`, SQLite database
files, virtual environments, and Python cache directories. `.dockerignore`
keeps the same local-only files out of Docker build context.

---

## Project Structure

```
logpulse/
├── api/            # FastAPI app, routes, SSE, pipeline orchestration
├── ingestion/      # Log simulator, parser, and ingestion pipeline
├── detection/      # Statistical Z-score anomaly detector
├── llm/            # Ollama/OpenAI enrichment layer
├── alerting/       # Webhook firing and payload construction
├── dashboard/      # Jinja2 templates + Chart.js frontend
├── db/             # SQLAlchemy models and CRUD operations
├── tests/          # Unit tests
├── .env.example    # Safe local configuration template
├── .dockerignore   # Docker build exclusions
├── config.py       # Central settings loader
├── main.py         # Entry point
├── test-logs.csv   # Sample logs for local ingestion tests
├── FAQ.md          # Reviewer-oriented questions and answers
├── prompts.md      # AI prompt audit log (Vibe Coding)
└── docker-compose.yml
```

---

## License

MIT — see [LICENSE](LICENSE)
