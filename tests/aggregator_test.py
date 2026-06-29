from workers.aggregator import aggregate_findings

ruff_out = [{"type": "style", "severity": "low", "file": "auth.py", "line": 7,
             "message": "unused import", "suggestion": "remove it", "source": "ruff"}]
bandit_out = [{"type": "security", "severity": "medium", "file": "auth.py", "line": 7,
               "message": "SQL injection", "suggestion": "use params", "source": "bandit"}]
semgrep_out = []

result = aggregate_findings(ruff_out, bandit_out, semgrep_out)
print(result)