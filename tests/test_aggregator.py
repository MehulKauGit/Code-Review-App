from workers.aggregator import aggregate_findings


def test_aggregate_merges_multiple_tools():
    ruff_out = [
        {
            "type": "style",
            "severity": "low",
            "file": "auth.py",
            "line": 5,
            "message": "Unused import",
            "suggestion": "Remove it",
            "source": "ruff",
        }
    ]
    bandit_out = [
        {
            "type": "security",
            "severity": "high",
            "file": "db.py",
            "line": 20,
            "message": "SQL Injection vulnerability",
            "suggestion": "Use parameterized queries",
            "source": "bandit",
        }
    ]
    semgrep_out = []
    llm_out = [
        {
            "type": "bug",
            "severity": "critical",
            "file": "auth.py",
            "line": 42,
            "message": "Hardcoded secret key",
            "suggestion": "Use env var",
            "source": "llm",
        }
    ]

    result = aggregate_findings(ruff_out, bandit_out, semgrep_out, llm_out)

    assert result["total"] == 3
    assert len(result["findings"]) == 3
    assert result["summary"]["critical"] == 1
    assert result["summary"]["high"] == 1
    assert result["summary"]["low"] == 1
    assert result["summary"]["medium"] == 0


def test_aggregate_deduplicates_overlapping_findings():
    # Both bandit and semgrep flag the exact same file, line, severity
    bandit_out = [
        {
            "type": "security",
            "severity": "high",
            "file": "auth.py",
            "line": 10,
            "message": "SQL injection detected",
            "suggestion": "Use params",
            "source": "bandit",
        }
    ]
    semgrep_out = [
        {
            "type": "security",
            "severity": "high",
            "file": "auth.py",
            "line": 10,
            "message": "Formatted SQL query detected",
            "suggestion": "Use ORM",
            "source": "semgrep",
        }
    ]

    result = aggregate_findings(bandit_out, semgrep_out)

    assert result["total"] == 1
    assert len(result["findings"]) == 1
    finding = result["findings"][0]
    assert finding["file"] == "auth.py"
    assert finding["line"] == 10
    assert finding["severity"] == "high"
    # Merged sources list
    assert "bandit" in finding["source"]
    assert "semgrep" in finding["source"]


def test_aggregate_empty_findings():
    result = aggregate_findings([], [], [])
    assert result["total"] == 0
    assert result["findings"] == []
    assert result["summary"] == {"critical": 0, "high": 0, "medium": 0, "low": 0}
