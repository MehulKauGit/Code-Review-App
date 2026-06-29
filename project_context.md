# Code Review API — Project Context

## What this project is

A Python-based code review service. POST a diff or file, get back structured feedback — bugs, security issues, style violations. Integrates with GitHub webhooks so it triggers automatically on pull requests.

---

## Tech stack

| Layer | Choice |
|-------|--------|
| Web framework | FastAPI |
| Task queue | Celery |
| Broker / result backend | Redis |
| Diff parsing | unidiff |
| Static analysis | ruff, bandit, semgrep |
| LLM review | Claude API (claude-sonnet-4-6) |
| GitHub integration | PyGithub + GitHub App auth |
| Database | Postgres (Cloud SQL) |
| Cloud | GCP — Cloud Run, Memorystore, Cloud SQL |
| Config | pydantic-settings |
| Logging | structlog |

---

## Project structure

```
code-review-api/
├── api/
│   ├── main.py            # FastAPI app factory
│   ├── config.py          # All env vars via pydantic-settings
│   ├── routes/
│   │   ├── review.py      # POST /review, GET /review/{job_id}
│   │   └── webhook.py     # POST /webhook/github
│   └── models/
│       ├── review.py      # ReviewRequest, ReviewResponse, Finding, ReviewResult
│       └── webhook.py     # PullRequestEvent, GitHubPullRequest, etc.
├── workers/
│   ├── celery_app.py      # Celery instance + config
│   ├── tasks.py           # run_review task (root orchestrator)
│   ├── parser.py          # Diff parsing with unidiff
│   ├── static.py          # ruff, bandit, semgrep runners
│   ├── aggregator.py      # Merge + deduplicate findings (not built yet)
│   └── scratch.py         # Throwaway test file (not committed)
├── tests/
│   └── test_review.py     # Phase 1 tests
├── pyproject.toml
├── docker-compose.yml     # Redis + Flower
├── Dockerfile
└── .env
```

---

## How a request flows

**Path 1 — Direct API call:**
```
Client POSTs a diff
→ FastAPI validates shape (Pydantic)
→ Generates a job ID (uuid4)
→ Queues run_review Celery task (returns 202 immediately)
→ Client polls GET /review/{job_id} for results
```

**Path 2 — GitHub webhook:**
```
Developer opens a PR
→ GitHub POSTs to /webhook/github
→ Verify HMAC-SHA256 signature (before parsing payload)
→ Filter event type (only pull_request) and action (opened/synchronize/reopened)
→ Extract diff_url + commit_sha
→ Queue run_review Celery task (returns 202 immediately)
```

Both paths converge at the same `run_review` Celery task.

---

## Finding schema

Every tool (ruff, bandit, semgrep, Claude) normalizes output to this shape:

```json
{
  "type": "bug | security | style | suggestion",
  "severity": "critical | high | medium | low",
  "file": "src/auth.py",
  "line": 42,
  "message": "Possible SQL injection via string concatenation",
  "suggestion": "Use parameterized queries",
  "source": "bandit | ruff | semgrep | llm"
}
```

---

## Key design decisions

- **Async by default** — analysis can take 5-30 seconds. HTTP layer never blocks. Returns job ID immediately, client polls.
- **Validate at the boundary** — Pydantic rejects bad input before it touches any logic.
- **Separate concerns** — `api/` owns HTTP only. `workers/` owns processing only. They don't know about each other except through the task interface.
- **Security first in webhook** — HMAC signature verified before JSON is parsed.
- **One config object** — nothing calls `os.getenv()` directly. Everything flows through `settings`.
- **Celery task_id == job_id** — so polling by job ID maps directly to Celery's AsyncResult without a DB lookup.

---

## Phases

### Phase 1 — Foundation ✅ COMPLETE
- FastAPI app with health check
- `POST /review` + `GET /review/{job_id}`
- GitHub webhook receiver with HMAC-SHA256 signature verification
- Celery + Redis task queue wired up
- Docker compose for local infrastructure (Redis + Flower)
- Pydantic models for all data shapes

**Status:** All endpoints working. Manually tested webhook with PowerShell Invoke-WebRequest. Two of three pytest tests pass (third blocked by Celery/Windows broker issue — skipped).

---

### Phase 2 — Analysis Pipeline 🔄 IN PROGRESS

**Goal:** Fill in the `run_review` stub with real analysis.

#### What's done:
- `workers/parser.py` — `parse_diff()` built and tested. Takes a raw diff string, returns list of `{filename, content, changed_lines}`. Uses `unidiff.PatchSet`.
- `workers/static.py` — `run_ruff()`, `run_bandit()`, `run_semgrep()` built. Each writes content to a temp file, runs the tool as subprocess, parses JSON output, normalizes to Finding schema, filters to changed lines only.
  - bandit: working, catches SQL injection ✅
  - ruff: working, catches style issues ✅
  - semgrep: Unicode encoding issue on Windows — fixed by adding `encoding="utf-8"` to subprocess call

#### What's left in Phase 2:
- `workers/aggregator.py` — merge findings from all tools, deduplicate (same file + line + severity = one finding), build summary dict
- Wire everything into `workers/tasks.py` — replace stub body with: fetch diff → parse → run tools → aggregate → return
- `fetch_diff()` helper — use `httpx` to fetch diff from GitHub's `diff_url`
- End-to-end test: POST bad Python code, get back real findings

---

### Phase 3 — LLM Integration (not started)
- Celery `llm` queue worker calling Claude API
- Send only changed hunks (not full file) to save tokens
- Structured output — bugs, logic issues, suggestions
- Merge LLM findings with static analysis output
- Token budget guard, retry with backoff on rate limits

---

### Phase 4 — GitHub Delivery (not started)
- GitHub App auth (JWT + installation token)
- Post inline PR review comments (line-level)
- Create GitHub Check Runs (shows pass/fail on PR)
- Handle re-runs — don't duplicate comments on same commit

---

### Phase 5 — Storage & Persistence (not started)
- Cloud SQL (Postgres) — SQLAlchemy async models
- Persist jobs, findings, webhook events
- `GET /history?repo=&branch=` endpoint
- Idempotency — same commit SHA returns cached result

---

### Phase 6 — Cloud Deployment (not started)
- Multi-stage Dockerfile
- Cloud Run for API + workers
- Cloud Memorystore (Redis)
- Cloud SQL
- Secret Manager for API keys
- CI/CD via Cloud Build

---

### Phase 7 — Hardening & Observability (not started)
- Structured logging with structlog + Cloud Logging
- Cloud Monitoring dashboards
- Sentry for error tracking
- Rate limiting on POST /review
- Input validation hardening (max diff size, file type allowlist)
- Load testing with locust

---

## Local dev setup

```powershell
# Activate venv
.venv\Scripts\Activate.ps1

# Terminal 1 — Redis
docker compose up redis

# Terminal 2 — Celery worker
python -m celery -A workers.celery_app worker --loglevel=info --queues=parse

# Terminal 3 — API
python -m uvicorn api.main:app --reload

# Run tests
python -m pytest tests/ -v

# Flower (Celery dashboard) — http://localhost:5555
# API docs — http://localhost:8000/docs (DEBUG=true only)
```

---

## Environment variables (.env)

```
DEBUG=true
LOG_LEVEL=INFO
GITHUB_WEBHOOK_SECRET=dev-secret
LLM_API_KEY=dev-key
REDIS_URL=redis://localhost:6379/0
```

---

## Current status summary

Entering a new chat? Here's where things stand:

**Phase 1 complete.** The HTTP layer, webhook receiver, and Celery plumbing are all working.

**Phase 2 in progress.** Diff parser and static analysis workers are built and tested in isolation. Next step is building `workers/aggregator.py`, then wiring everything into `workers/tasks.py` to complete the end-to-end pipeline.
