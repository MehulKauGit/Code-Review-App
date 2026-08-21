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

def post_inline_comments(repo: str, pull_number: int, commit_sha: str, findings: list) -> None:
    headers = get_headers()
    for finding in findings:
        if not finding.get("line"):
            continue
        body = f"**[{finding['severity'].upper()}] {finding['type']}**\n\n{finding['message']}"
        if finding.get("suggestion"):
            body += f"\n\n💡 {finding['suggestion']}"
        httpx.post(
            f"{BASE}/repos/{repo}/pulls/{pull_number}/comments",
            headers=headers,
            json={
                "body": body,
                "commit_id": commit_sha,
                "path": finding["file"],
                "line": finding["line"],
            },
            follow_redirects=True
        ).raise_for_status()

def post_summary_comment(repo: str, pull_number: int, summary: dict, total: int) -> None:
    lines = ["## Code Review Bot Summary\n"]
    for severity, count in summary.items():
        lines.append(f"- **{severity}:** {count}")
    lines.append(f"\n**Total findings: {total}**")
    body = "\n".join(lines)

    httpx.post(
        f"{BASE}/repos/{repo}/issues/{pull_number}/comments",
        headers=get_headers(),
        json={"body": body},
        follow_redirects=True,
    ).raise_for_status()

