import httpx

from workers.github_client import get_installation_token

BASE= "https://api.github.com"

def get_headers() -> dict:
    token = get_installation_token()
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
def create_check_run(repo:str,commit_sha:str)-> int:
    response=httpx.post(
        f"{BASE}/repos/{repo}/check-runs",
        headers=get_headers(),
        json={
            "name":"Code Review Bot",
            "head_sha":commit_sha,
            "status":"in_progress",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        follow_redirects=True
    )
    response.raise_for_status()
    return response.json()["id"]

def complete_check_run(repo:str,check_run_id: int,conclusion: str,summary: str)-> None:
    response =httpx.patch(
        f"{BASE}/repos/{repo}/check-runs/{check_run_id}",
        headers=get_headers(),
        json={
            "status":"completed",
            "conclusion":conclusion,
            "output":{
                "title":"Code Review Results",
                "summary":summary,
            }
        },
        follow_redirects=True
    )
    response.raise_for_status()

def post_pr_comment(repo: str, pull_number: int, findings: list, summary: dict, total: int) -> None:
    lines = ["## Code Review Bot Results\n"]
    
    for severity in ["critical", "high", "medium", "low"]:
        severity_findings = [f for f in findings if f["severity"] == severity]
        if not severity_findings:
            continue
        lines.append(f"### {severity.upper()}")
        for f in severity_findings:
            lines.append(f"- **{f['file']} line {f['line']}** — {f['message']}")
            if f.get("suggestion"):
                lines.append(f"  - 💡 {f['suggestion']}")
        lines.append("")

    lines.append(f"**Total: {total} findings** — " + ", ".join(f"{v} {k}" for k,v in summary.items() if v))

    httpx.post(
        f"{BASE}/repos/{repo}/issues/{pull_number}/comments",
        headers=get_headers(),
        json={"body": "\n".join(lines)},
    ).raise_for_status()
