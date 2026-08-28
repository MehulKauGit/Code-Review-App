import hashlib
import hmac
import json
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from api.main import create_app
from api.config import settings
import api.routes.webhook as webhook_route

client = TestClient(create_app())


def _generate_sig(payload: bytes, secret: str = settings.github_webhook_secret) -> str:
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


VALID_PAYLOAD = {
    "action": "opened",
    "number": 42,
    "pull_request": {
        "number": 42,
        "head": {"sha": "abc1234", "ref": "feature-branch"},
        "base": {"sha": "def5678", "ref": "main"},
        "diff_url": "https://github.com/owner/repo/pull/42.diff",
    },
    "repository": {
        "full_name": "owner/repo",
        "default_branch": "main",
    },
}


def test_webhook_missing_signature():
    payload_bytes = json.dumps(VALID_PAYLOAD).encode()
    r = client.post(
        "/webhook/github",
        content=payload_bytes,
        headers={"X-GitHub-Event": "pull_request"},
    )
    assert r.status_code == 401
    assert "Missing signature header" in r.json()["detail"]


def test_webhook_malformed_signature():
    payload_bytes = json.dumps(VALID_PAYLOAD).encode()
    r = client.post(
        "/webhook/github",
        content=payload_bytes,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "invalid_format_no_sha_prefix",
        },
    )
    assert r.status_code == 401
    assert "Malformed signature" in r.json()["detail"]


def test_webhook_invalid_signature():
    payload_bytes = json.dumps(VALID_PAYLOAD).encode()
    wrong_sig = _generate_sig(payload_bytes, secret="wrong-secret-key")
    r = client.post(
        "/webhook/github",
        content=payload_bytes,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": wrong_sig,
        },
    )
    assert r.status_code == 401
    assert "Invalid signature" in r.json()["detail"]


def test_webhook_ignores_non_pull_request_events():
    payload_bytes = json.dumps(VALID_PAYLOAD).encode()
    sig = _generate_sig(payload_bytes)
    r = client.post(
        "/webhook/github",
        content=payload_bytes,
        headers={
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": sig,
        },
    )
    assert r.status_code == 202
    assert r.json()["status"] == "ignored"
    assert "push" in r.json()["reason"]


def test_webhook_ignores_unsupported_pr_action():
    unsupported_payload = {**VALID_PAYLOAD, "action": "closed"}
    payload_bytes = json.dumps(unsupported_payload).encode()
    sig = _generate_sig(payload_bytes)
    r = client.post(
        "/webhook/github",
        content=payload_bytes,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": sig,
        },
    )
    assert r.status_code == 202
    assert r.json()["status"] == "ignored"
    assert "closed" in r.json()["reason"]


def test_webhook_queues_supported_pr_event(monkeypatch):
    mock_task = MagicMock()
    monkeypatch.setattr(webhook_route, "run_review", mock_task)

    payload_bytes = json.dumps(VALID_PAYLOAD).encode()
    sig = _generate_sig(payload_bytes)
    r = client.post(
        "/webhook/github",
        content=payload_bytes,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": sig,
        },
    )
    assert r.status_code == 202
    assert r.json()["status"] == "queued"
    assert "job_id" in r.json()
    assert mock_task.apply_async.called
