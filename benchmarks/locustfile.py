"""Locust load testing suite for Code Review App.

Usage:
    locust -f benchmarks/locustfile.py --host http://localhost:8000
"""

import uuid
from locust import HttpUser, between, task

SAMPLE_DIFF = """diff --git a/src/sample.py b/src/sample.py
--- a/src/sample.py
+++ b/src/sample.py
@@ -1,3 +1,5 @@
 import os
+import sys
+def run_review():
+    return True
"""


class CodeReviewUser(HttpUser):
    wait_time = between(0.1, 1.0)
    api_key = "dev-api-key"

    def on_start(self):
        self.headers = {"X-API-Key": self.api_key}
        self.recent_job_ids = []

    @task(4)
    def submit_code_review(self):
        """Simulate submitting a code review diff."""
        commit_sha = f"sha-{uuid.uuid4().hex[:8]}"
        payload = {
            "diff": SAMPLE_DIFF,
            "repo": "owner/load-test-repo",
            "commit_sha": commit_sha,
        }
        with self.client.post("/review", json=payload, headers=self.headers, catch_response=True) as resp:
            if resp.status_code in [200, 202]:
                data = resp.json()
                if "job_id" in data:
                    self.recent_job_ids.append(data["job_id"])
                    if len(self.recent_job_ids) > 10:
                        self.recent_job_ids.pop(0)
                resp.success()
            elif resp.status_code == 429:
                resp.success()  # 429 is expected when rate limits are triggered under high load
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(3)
    def poll_job_status(self):
        """Simulate client polling for completed review results."""
        if not self.recent_job_ids:
            return

        job_id = self.recent_job_ids[-1]
        with self.client.get(f"/review/{job_id}", headers=self.headers, catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Failed to fetch job {job_id}: {resp.status_code}")

    @task(2)
    def check_review_history(self):
        """Simulate querying historical job pagination."""
        with self.client.get("/review/history?page=1&page_size=10", headers=self.headers, catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"History query failed: {resp.status_code}")

    @task(1)
    def probe_health_and_readiness(self):
        """Simulate infrastructure health probes."""
        self.client.get("/health")
        self.client.get("/ready")
