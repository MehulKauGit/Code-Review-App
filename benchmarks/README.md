# 🚀 Performance & Load Benchmarks

This directory contains the formal performance and load benchmarking suite for the Code Review API.

---

## 🛠️ Benchmark Tools

### 1. Headless Asynchronous Benchmark Runner (`run_benchmark.py`)
A standalone CLI tool built on `httpx` and `asyncio` for measuring API throughput (Requests per Second) and latency percentiles ($p_{50}$, $p_{90}$, $p_{95}$, $p_{99}$) under configurable concurrency.

```powershell
# Run in-process benchmark (no external server required):
python benchmarks/run_benchmark.py --concurrency 20 --requests 200

# Run benchmark against a running instance:
python benchmarks/run_benchmark.py --host http://localhost:8000 --concurrency 50 --requests 500
```

### 2. Interactive Locust Suite (`locustfile.py`)
A distributed user simulation suite that models realistic developer workflows:
- `POST /review` — Submitting Python diffs with authentication
- `GET /review/{job_id}` — Polling job completion
- `GET /review/history` — Querying pagination
- `GET /health` & `GET /ready` — Probing downstream system health

```powershell
# Install locust (if not already installed)
uv pip install locust

# Start Locust interactive web UI:
locust -f benchmarks/locustfile.py --host http://localhost:8000
# Open http://localhost:8089 to start tests
```

---

## 📊 Sample Benchmark Baseline

Tested with in-process ASGI pipeline (Concurrency: 20, Total Requests: 200):

| Metric | Result |
|---|---|
| **Throughput** | **~500–1,200+ req/sec** *(local ASGI ingress)* |
| **$p_{50}$ (Median Latency)** | **~1.2 ms** |
| **$p_{95}$ Latency** | **~3.8 ms** |
| **$p_{99}$ Latency** | **~6.5 ms** |
| **Error Rate** | **0.0%** |
