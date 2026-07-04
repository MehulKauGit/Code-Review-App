import httpx
from celery import shared_task
from workers.parser import parse_diff
from workers.celery_app import celery_app
from workers.static import run_ruff , run_bandit, run_semgrep
from workers.aggregator import aggregate_findings
from workers.llm import run_llm_review  

def fetch_diff(diff_url:str)-> str:
    response=httpx.get(diff_url,timeout=10.0)
    response.raise_for_status()
    return response.text

@shared_task(bind=True, name="workers.tasks.run_review", max_retries=3)
def run_review(
    self,
    job_id: str,
    diff: str | None = None,
    diff_url: str | None = None,
    content: str | None = None,
    filename: str | None = None,
    **kwargs,
    ):
    if diff_url and not diff:
        diff = fetch_diff(diff_url)
    if diff:
        parsed_files = parse_diff(diff)

    elif content and filename:
        parsed_files = [
            {
                "filename": filename,
                "content": content,
                "changed_lines": list(range(1, content.count("\n") + 2))
            }
        ]

    else:
        raise ValueError(
            "Either diff/diff_url or content+filename must be provided"
        )

    ruff_findings=[]
    bandit_findings=[]
    semgrep_findings=[]
     
    for file in parsed_files:       
         ruff_findings += run_ruff(file["filename"], file["content"], file["changed_lines"])
         bandit_findings += run_bandit(file["filename"], file["content"], file["changed_lines"])
         semgrep_findings += run_semgrep(file["filename"], file["content"], file["changed_lines"])

    llm_findings=run_llm_review(parsed_files)
    
    result = aggregate_findings(ruff_findings, bandit_findings, semgrep_findings)
    return result
    