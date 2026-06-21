# generate_sig.py — run this once to get a test signature
import hashlib, hmac, json

secret = "dev-secret"
payload = json.dumps({
    "action": "opened",
    "number": 1,
    "pull_request": {
        "number": 1,
        "head": {"sha": "abc123", "ref": "feature/test"},
        "base": {"sha": "def456", "ref": "main"},
        "diff_url": "https://github.com/owner/repo/pull/1.diff"
    },
    "repository": {
        "full_name": "owner/repo",
        "default_branch": "main"
    }
})

sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
print(f"sha256={sig}")
print(payload)