from fastapi.testclient import TestClient
from api.main import create_app

client = TestClient(create_app())

def test_review_rejects_empty_payload():
    r = client.post("/review", json={})
    assert r.status_code == 422

def test_review_rejects_missing_diff_and_content():
    r = client.post("/review", json={"repo": "owner/repo"})
    assert r.status_code == 422

def test_review_accepts_diff(monkeypatch):
    import api.routes.review as review_module
    monkeypatch.setattr(review_module.run_review, "apply_async", lambda *a, **kw: None)
    r = client.post("/review", json={"diff": "--- a/foo.py\n+++ b/foo.py"})
    assert r.status_code == 202
    assert r.json()["status"] == "queued"
    assert "job_id" in r.json()