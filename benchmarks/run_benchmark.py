"""High-performance asynchronous benchmark runner.

Measures throughput (RPS), concurrency scaling, and latency percentiles (p50, p90, p95, p99).

Usage:
    # Benchmark in-process FastAPI app directly (no running server required):
    python benchmarks/run_benchmark.py --concurrency 20 --requests 200

    # Benchmark running HTTP server:
    python benchmarks/run_benchmark.py --host http://localhost:8000 --concurrency 50 --requests 500
"""

import argparse
import asyncio
import time
import uuid
import statistics
import httpx
from unittest.mock import AsyncMock, MagicMock

SAMPLE_DIFF = """diff --git a/src/auth.py b/src/auth.py
--- a/src/auth.py
+++ b/src/auth.py
@@ -1,3 +1,5 @@
 import os
+import secrets
+def verify_token(token):
+    return True
"""


async def run_worker(
    client: httpx.AsyncClient,
    request_queue: asyncio.Queue,
    latencies: list[float],
    status_counts: dict[int, int],
    api_key: str,
):
    headers = {"X-API-Key": api_key}
    while not request_queue.empty():
        try:
            req_type = await request_queue.get()
            start_time = time.perf_counter()

            if req_type == "submit_review":
                payload = {
                    "diff": SAMPLE_DIFF,
                    "repo": "owner/benchmark-repo",
                    "commit_sha": f"sha-{uuid.uuid4().hex[:8]}",
                }
                resp = await client.post("/review", json=payload, headers=headers)
            elif req_type == "health":
                resp = await client.get("/health")
            elif req_type == "ready":
                resp = await client.get("/ready")
            else:
                resp = await client.get("/review/history", headers=headers)

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            latencies.append(elapsed_ms)

            code = resp.status_code
            if code not in [200, 202, 429]:
                print(f"[!] Unexpected status {code}: {resp.text}")
            status_counts[code] = status_counts.get(code, 0) + 1


        except Exception:
            status_counts[599] = status_counts.get(599, 0) + 1
        finally:
            request_queue.task_done()


def calculate_percentile(sorted_list: list[float], percentile: float) -> float:
    if not sorted_list:
        return 0.0
    k = (len(sorted_list) - 1) * (percentile / 100.0)
    f = int(k)
    c = f + 1
    if c < len(sorted_list):
        return sorted_list[f] + (k - f) * (sorted_list[c] - sorted_list[f])
    return sorted_list[f]


async def execute_benchmark(host: str | None, concurrency: int, total_requests: int, api_key: str):
    latencies: list[float] = []
    status_counts: dict[int, int] = {}

    queue: asyncio.Queue = asyncio.Queue()
    for i in range(total_requests):
        # 60% review submits, 20% health probes, 20% history checks
        if i % 10 < 6:
            queue.put_nowait("submit_review")
        elif i % 10 < 8:
            queue.put_nowait("health")
        else:
            queue.put_nowait("history")

    print("\n=======================================================")
    print(" [*] Running Load Benchmark")
    print(f" Target: {'In-Process ASGI App' if not host else host}")
    print(f" Total Requests: {total_requests} | Concurrency: {concurrency}")
    print("=======================================================\n")

    start_total = time.perf_counter()

    if host:
        async with httpx.AsyncClient(base_url=host, timeout=30.0) as client:
            workers = [
                asyncio.create_task(run_worker(client, queue, latencies, status_counts, api_key))
                for _ in range(concurrency)
            ]
            await queue.join()
            for w in workers:
                w.cancel()
    else:
        # In-process benchmark against FastAPI app with isolated dependencies
        from api.main import create_app
        from api.deps import get_db
        from api.limiter import RateLimiter
        import api.routes.review as review_route

        app = create_app()

        class MockResult:
            def scalars(self):
                return self
            def first(self):
                return None
            def all(self):
                return []

        async def mock_get_db():
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value=MockResult())
            mock_session.get = AsyncMock(return_value=None)
            yield mock_session

        app.dependency_overrides[get_db] = mock_get_db
        review_route.run_review = MagicMock()

        from fastapi import Request, Response

        # Mock RateLimiter to evaluate pure framework/routing/serialization latency
        async def mock_limiter_call(self, request: Request, response: Response):
            response.headers["X-RateLimit-Limit"] = "100"
            response.headers["X-RateLimit-Remaining"] = "99"
            response.headers["X-RateLimit-Reset"] = "60"

        RateLimiter.__call__ = mock_limiter_call


        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=30.0) as client:
            workers = [
                asyncio.create_task(run_worker(client, queue, latencies, status_counts, api_key))
                for _ in range(concurrency)
            ]
            await queue.join()
            for w in workers:
                w.cancel()


    duration = time.perf_counter() - start_total
    rps = total_requests / duration if duration > 0 else 0.0

    sorted_latencies = sorted(latencies)
    avg_latency = statistics.mean(sorted_latencies) if sorted_latencies else 0.0
    p50 = calculate_percentile(sorted_latencies, 50.0)
    p90 = calculate_percentile(sorted_latencies, 90.0)
    p95 = calculate_percentile(sorted_latencies, 95.0)
    p99 = calculate_percentile(sorted_latencies, 99.0)
    min_lat = sorted_latencies[0] if sorted_latencies else 0.0
    max_lat = sorted_latencies[-1] if sorted_latencies else 0.0

    print("[+] Benchmark Results Summary:")
    print("-" * 55)
    print(f" Completed Requests : {len(latencies)} / {total_requests}")
    print(f" Total Duration     : {duration:.2f} seconds")
    print(f" Throughput         : {rps:.1f} req/sec")
    print("-" * 55)
    print(" Latency (ms):")
    print(f"   Min / Avg / Max  : {min_lat:.2f} ms / {avg_latency:.2f} ms / {max_lat:.2f} ms")
    print(f"   p50 (Median)     : {p50:.2f} ms")
    print(f"   p90              : {p90:.2f} ms")
    print(f"   p95              : {p95:.2f} ms")
    print(f"   p99              : {p99:.2f} ms")
    print("-" * 55)
    print(" HTTP Status Codes  :")
    for code, count in sorted(status_counts.items()):
        status_label = "OK/Accepted" if code in [200, 202] else ("Rate Limited" if code == 429 else "Error")
        print(f"   HTTP {code} ({status_label}): {count} ({count / total_requests * 100:.1f}%)")
    print("=======================================================\n")



def main():
    parser = argparse.ArgumentParser(description="Code Review App Benchmark Runner")
    parser.add_argument("--host", type=str, default=None, help="Base URL of running server (e.g. http://localhost:8000)")
    parser.add_argument("--concurrency", type=int, default=20, help="Number of concurrent client workers")
    parser.add_argument("--requests", type=int, default=200, help="Total number of requests to execute")
    parser.add_argument("--api-key", type=str, default="dev-api-key", help="API Key for authentication")
    args = parser.parse_args()

    asyncio.run(execute_benchmark(args.host, args.concurrency, args.requests, args.api_key))


if __name__ == "__main__":
    main()
