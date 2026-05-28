# LogPulse FAQ

## Does LogPulse satisfy the assessment requirement?

Yes. LogPulse implements the selected project: **Intelligent Observability & Event Watchdog**. It is Python-based, API-first, uses SQLite as a free database, ingests logs, detects error spikes, triggers a simulated webhook alert, and visualizes health trends in a dashboard.

## Are anomalies detected by the LLM?

No. Anomalies are detected by a deterministic statistical gate. The detector uses a sliding window, current error rate, and Z-score threshold to identify spikes.

The LLM is used after detection to enrich confirmed anomalies with:
- root cause hypothesis
- severity
- suggested remediation action

## Why use a hybrid statistical + LLM approach?

For observability systems, deterministic detection is usually safer and easier to explain. Thresholds and Z-scores make anomaly triggers reproducible and testable.

The LLM is better used for semantic reasoning after a signal is confirmed. This avoids calling the model for every log line, reduces latency and cost, and keeps the detection path predictable.

## How does this relate to the requirement to use AI logic?

The AI component is part of the anomaly workflow. LogPulse uses statistical logic to detect the spike, then uses a local LLM to analyze the anomaly and produce SRE-style context and remediation guidance.

A concise description is:

> LogPulse uses statistical anomaly detection with LLM-based semantic enrichment.

## What log sources are supported?

LogPulse supports three ingestion paths:
- simulator-generated logs for demos
- file tailing with `LOG_SOURCE=file`
- API ingestion through `POST /api/logs`

The parser accepts structured JSON logs, common text log lines, and less-structured fallback lines.

## How do I test ingestion quickly?

Start the app:

```powershell
python main.py
```

Open the dashboard:

```text
http://localhost:8000
```

Then ingest the sample CSV:

```powershell
Import-Csv .\test-logs.csv | ForEach-Object {
  Invoke-RestMethod `
    -Method Post `
    -Uri http://localhost:8000/api/logs `
    -ContentType "application/json" `
    -Body (@{ raw = $_.raw } | ConvertTo-Json)
}
```

## What should happen when the sample CSV is ingested?

The dashboard should show live logs, update the error-rate trend, and display anomalies when the payment-service error spike crosses the configured thresholds.

## Is the webhook real?

It is intentionally simulated. The app posts anomaly alerts to its own `/webhook/receiver` endpoint. This demonstrates the alerting workflow without requiring Slack, PagerDuty, Teams, or any paid external service.

## Which database is used?

SQLite is used through SQLAlchemy async. Local runs use `logpulse.db` by default. Docker runs persist the database under `/app/data/logpulse.db` through the configured Docker volume.

## What should not be committed to GitHub?

Do not commit `.env`, local SQLite database files, virtual environments, Python cache directories, or pytest cache output. The repository includes `.env.example` for safe configuration sharing, plus `.gitignore` and `.dockerignore` rules for local-only files.

## Can this run without OpenAI?

Yes. The primary LLM provider is local Ollama. OpenAI is only an optional fallback if configured. If no LLM provider is reachable, the app still detects and records anomalies with a safe fallback enrichment.

## What are the main API endpoints?

- `GET /` - dashboard
- `POST /api/logs` - ingest one raw or structured log
- `GET /api/logs` - recent logs
- `GET /api/anomalies` - detected anomalies
- `GET /api/stats` - aggregate log-level counts
- `GET /api/timeseries` - health trend data
- `POST /webhook/receiver` - simulated alert receiver
- `GET /health` - health check

## What is intentionally out of scope?

This is an MVP. Production features such as authentication, multi-tenant access control, alert acknowledgement workflows, long-term metrics storage, and external alert integrations are not included.
