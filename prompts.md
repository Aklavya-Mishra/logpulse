# LogPulse — Prompt Audit Log (`prompts.md`)

> This file is maintained as required by the Vibe Coding workflow.
> All architectural decisions and build instructions are logged here in sequence.
> No code was written or edited manually — all logic was produced by the AI agent (Claude).

---

## Prompt #1 — Initial Execution (Architecture Scoping)

**Role:** Lead Architect mode: ON.

> "Lead Architect mode: ON. We are building a Python-based, API-first Intelligent Observability & Event Watchdog using a free database and a dashboard.
> Rules:
> 1. No Manual Edits: You provide all logic and fixes. I will not edit any code.
> 2. Audit Log: You must maintain a file named prompts.md. After every turn, update that file with the prompt I just used.
> 3. Time-Check: Start a timer. Goal is an MVP in 4-6 hours (Max window: 16h). Report 'Elapsed Time' at the end of every response.
> Acknowledge and let's start."

**AI Response:** Acknowledged. MVP-scoped architecture Q&A initiated. Goal: lean, deployable, demonstrable in a single `docker-compose up`.

---

## Prompt #2 — LLM Model Selection

> "For the Ollama primary layer, which model should we use? Keep it MVP — something that runs well locally without heavy VRAM requirements."

**Decision locked:** Ollama `llama3.1:8b` (primary). Lightweight, fast inference, fits comfortably in 16GB VRAM. OpenAI `gpt-4o-mini` retained as optional env-configured fallback — not a hard dependency.

---

## Prompt #3 — Log Ingestion Source

> "For MVP, what's the simplest log source that lets us demo the full pipeline without any external setup?"

**Decision locked:** Simulated log generator only. Generates realistic INFO/WARN/ERROR/CRITICAL entries with configurable spike probability. Switchable via `LOG_SOURCE` env var for future extensibility. No file watcher needed for MVP scope.

---

## Prompt #4 — Anomaly Detection Strategy

> "What detection approach gives us the best signal without overcomplicating the MVP?"

**Decision locked:** Hybrid statistical gate — sliding window Z-score + error rate threshold. LLM enrichment called only on confirmed anomaly, never on every log entry. Keeps inference cost near-zero during normal operation.

---

## Prompt #5 — Dashboard & Frontend

> "What's the simplest frontend that still looks production-quality and requires zero build tooling?"

**Decision locked:** FastAPI + Jinja2 + Chart.js, SSE-powered live updates. Single HTML file, no npm, no React build step. Entire project runs as one Python process.

---

## Prompt #6 — Webhook Alerting

> "For MVP alerting, keep it self-contained — no Slack accounts, no PagerDuty setup."

**Decision locked:** Self-contained simulated webhook receiver at `/webhook/receiver`. Alert fires, receiver logs it, zero external dependency. Real integration targets (Slack/Discord) are post-MVP.

---

## Prompt #7 — Database Schema

> "Keep the schema minimal for MVP — just what's needed to power the dashboard and store anomalies."

**Decision locked:** Two tables — `logs` and `anomalies`. Anomalies table includes LLM enrichment columns (root cause, severity, suggested action, provider used) and webhook delivery status. Resolution tracking, health snapshots, and delivery history are post-MVP scope.

---

## Prompt #8 — Project Structure

> "What's the right structure for an MVP that's still clean enough to open-source?"

**Decision locked:** Modular monorepo — `ingestion/`, `detection/`, `llm/`, `alerting/`, `dashboard/`, `db/`, `api/`. Each module independently testable. Single entry point via `main.py`.

---

## Prompt #9 — Testing Strategy

> "What level of testing makes sense for an MVP without over-investing in test infrastructure?"

**Decision locked:** Unit tests only — pytest covering anomaly detector, log simulator, LLM response parsing, webhook payload construction. Mocked LLM calls, no external services required to run the suite. Integration tests are post-MVP.

---

## Prompt #10 — Documentation

> "What docs do we need at MVP to make this submittable and open-source-ready?"

**Decision locked:** `README.md` (setup + usage), inline docstrings on all modules and functions, `prompts.md` (this file), and `ARCHITECTURE.md` with Mermaid diagrams as the submission architecture artifact. `CONTRIBUTING.md` is post-MVP.

---

## Prompt #11 — Project Name

> "logpulse"

**Decision locked:** Project name `logpulse`. Used as repo name, Docker image name, and dashboard title.

---

## Prompt #12 — Full Build Execution

> "Yes please. And forget about the external tasks like tagle.ai, I'll take care of that."

**Build executed:** Full end-to-end MVP built by AI agent across the following files:
- `requirements.txt`
- `.env.example`
- `config.py`
- `db/models.py`
- `db/crud.py`
- `ingestion/simulator.py`
- `ingestion/pipeline.py`
- `detection/detector.py`
- `llm/enrichment.py`
- `alerting/webhook.py`
- `dashboard/templates/index.html`
- `api/app.py`
- `main.py`
- `tests/test_unit.py`
- `pytest.ini`
- `Dockerfile`
- `docker-compose.yml`
- `.gitignore`
- `README.md`
- `ARCHITECTURE.md`
- `LICENSE`
- `prompts.md` (this file)

**Test result:** 18/18 unit tests passing.

**Elapsed Time: ~45 minutes (architectural scoping + full build)**

---

## Prompt #13 - Requirement Gap Review

> "So, this was the task. Go through the codebase and tell me if all the requirements are met or are we having gaps in terms of requirements."

**Review completed:** Compared the assessment requirements against the codebase. Core Project 3 functionality was present, but implementation gaps were identified: real log parsing, API-based log ingestion, LLM timeout safety, Docker SQLite persistence, and documentation alignment.

---

## Prompt #14 - Implementation Scope Confirmation

> "forget tagle and github thing, we'll do it later. for now, I want to focus on the implementation of the requirements."

**Decision locked:** Excluded Tagle, GitHub, and final-submission packaging from immediate scope. Focus narrowed to implementation requirements only.

---

## Prompt #15 - Requirement Completion Implementation

> "can you implement all the requirements as identified? If yes, I want you to add/update only what's required. if you feel that the entire code is to be done, do it but safely."

**Implementation executed:** Focused updates were made without rebuilding the app:
- Added `ingestion/parser.py` for JSON, raw text, and structured API log normalization.
- Updated `ingestion/pipeline.py` to support `LOG_SOURCE=file` through file tailing.
- Added `POST /api/logs` in `api/app.py` for external log ingestion.
- Added LLM enrichment timeout handling and `LLM_ENRICHMENT_TIMEOUT_SECONDS`.
- Fixed Docker SQLite persistence to `/app/data/logpulse.db`.
- Updated `README.md` and `ARCHITECTURE.md`.
- Added tests for parsing and API ingestion.

**Test result:** 23/23 unit tests passing.

---

## Prompt #16 - Local Run and Test Instructions

> "tell me how to run and test it locally"

**Guidance provided:** Documented local run commands, dashboard URL, pytest command, and example `POST /api/logs` request.

---

## Prompt #17 - Sample Log Data

> "can you generate a file, anything a csv or something with 100 logs in it and add it as test-logs.csv, so i can use it to test the code."

**Artifact added:** Created `test-logs.csv` with 100 sample log rows, including normal traffic and a payment-service error spike for anomaly testing.

---

## Prompt #18 - Dashboard CSV Ingestion Guidance

> "my question is, how can i ingent this in the dashboard."

**Guidance provided:** Explained that the CSV is ingested through `POST /api/logs` while the dashboard listens to SSE updates, and provided a PowerShell `Import-Csv` command to stream rows into the running app.

---

## Prompt #19 - Documentation Refresh

> "any documentation needs to be updated? as per the new changes in codebase. please change only what's required."

**Documentation updated:** Added sample-log ingestion instructions, `POST /api/logs` payload example, `test-logs.csv` project-structure entry, `.env` timeout setting, and an architecture sequence diagram update for simulator/file/API sources.

---

## Prompt #20 - Database Verification

> "so, is the db working in backend for all the changes in the data done?"

**Verification completed:** Ran a backend smoke test with a temporary SQLite database. Confirmed log insert/read, aggregate stats, timeseries generation, anomaly insert/read, LLM fields, and webhook status persistence.

**Smoke result:** `logs=1`, `stats_total=1`, `timeseries_points=1`, `anomalies=1`.

---

## Prompt #21 - Prompt Audit Refresh

> "any changes required in prompts.md based on current codebase."

**Audit log updated:** Appended the post-MVP review, implementation, documentation, sample data, dashboard ingestion, and database verification prompts so this file reflects the current codebase state.

---

## Prompt #22 - Reviewer FAQ

> "Can you add some FAQs as something faq.md where you have some generic questions and answers that reviewer might look for. something as discussed above, as why hybrid and so on."

**Artifact added:** Created `FAQ.md` with reviewer-oriented questions covering requirement fit, hybrid statistical + LLM design, supported log sources, sample CSV ingestion, webhook simulation, database behavior, API endpoints, and MVP scope.

---

## Prompt #23 - Final Documentation Consistency Pass

> "Can you update all the documents with the changes we have done or are they updated already?"

**Documentation checked and updated:** Confirmed the main documentation is aligned with the current codebase. Added an explicit `FAQ.md` reference in `README.md` and documented LLM enrichment timeout/fallback behavior in `ARCHITECTURE.md`.

---

## Prompt #24 - Pre-Push Documentation and Repository Hygiene

> "before pushing, update the documentations accordingly, one final time."

**Documentation updated:** Added repository hygiene guidance to `README.md` and `FAQ.md`, covering `.env.example`, ignored local secrets, SQLite database files, virtual environments, Python caches, pytest cache output, and Docker build exclusions.

---

## Estimated Build Time

**Initial MVP:** ~45 minutes for architectural scoping, implementation, docs, and initial tests.

**Requirement tightening pass:** ~75 minutes for requirement review, parser/API/file ingestion updates, timeout handling, Docker persistence fix, sample CSV generation, documentation updates, and verification.

**Total estimated time:** ~2 hours.
