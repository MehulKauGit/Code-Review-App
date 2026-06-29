# workers/static.py
import json
import os
import subprocess
import tempfile


def _write_temp_file(content: str, suffix: str = ".py") -> str:
    """Write content to a temp file, return the path."""
    with tempfile.NamedTemporaryFile(
        suffix=suffix,
        mode="w",
        delete=False,
        encoding="utf-8"
    ) as f:
        f.write(content)
        return f.name


def run_ruff(filename: str, content: str, changed_lines: list[int]) -> list[dict]:
    tmp = _write_temp_file(content)
    findings = []

    try:
        result = subprocess.run(
            ["ruff", "check", "--output-format=json", tmp],
            capture_output=True,
            text=True,
        )
        items = json.loads(result.stdout or "[]")
        for item in items:
            line = item.get("location", {}).get("row")
            if line not in changed_lines:
                continue
            findings.append({
                "type": "style",
                "severity": "low",
                "file": filename,
                "line": line,
                "message": item.get("message", ""),
                "suggestion": item.get("fix", {}).get("message") if item.get("fix") else None,
                "source": "ruff",
            })
    finally:
        os.unlink(tmp)

    return findings


def run_bandit(filename: str, content: str, changed_lines: list[int]) -> list[dict]:
    tmp = _write_temp_file(content)
    findings = []

    try:
        result = subprocess.run(
            ["bandit", "-f", "json", tmp],
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout or "{}")
        for item in data.get("results", []):
            line = item.get("line_number")
            if line not in changed_lines:
                continue
            findings.append({
                "type": "security",
                "severity": item.get("issue_severity", "medium").lower(),
                "file": filename,
                "line": line,
                "message": item.get("issue_text", ""),
                "suggestion": item.get("more_info"),
                "source": "bandit",
            })
    finally:
        os.unlink(tmp)

    return findings


def run_semgrep(filename: str, content: str, changed_lines: list[int]) -> list[dict]:
    tmp = _write_temp_file(content)
    findings = []

    try:
        result = subprocess.run(
            ["semgrep", "--config=p/python", "--json", tmp],
            capture_output=True,
            text=True,
            encoding="utf-8" 
        )
        data = json.loads(result.stdout or "{}")
        for item in data.get("results", []):
            line = item.get("start", {}).get("line")
            if line not in changed_lines:
                continue
            findings.append({
                "type": "security",
                "severity": item.get("extra", {}).get("severity", "medium").lower(),
                "file": filename,
                "line": line,
                "message": item.get("extra", {}).get("message", ""),
                "suggestion": None,
                "source": "semgrep",
            })
    finally:
        os.unlink(tmp)

    return findings