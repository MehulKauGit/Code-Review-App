import asyncio
from datetime import datetime
import httpx
import structlog
from celery import shared_task
from workers.parser import parse_diff
from workers.static import run_ruff, run_bandit, run_semgrep
from workers.aggregator import aggregate_findings
from workers.llm import run_llm_review
from workers.github_poster import create_check_run, complete_check_run, post_pr_comment
from api.database import AsyncSessionLocal
from api.models.db import Job, Finding, JobStatus

logger = structlog.get_logger()



def fetch_diff(diff_url: str) -> str:
    response = httpx.get(diff_url, timeout=10.0, follow_redirects=True)
    response.raise_for_status()
    return response.text


async def _create_job(job_id: str, repo: str | None, commit_sha: str | None, pull_number: int | None):
    async with AsyncSessionLocal() as db:
        job = Job(
            id=job_id,
            repo=repo or "",
            commit_sha=commit_sha or "",
            pull_number=pull_number,
            status=JobStatus.RUNNING.value,
        )
        db.add(job)
        await db.commit()


async def _complete_job(job_id: str, findings: list[dict]):
    async with AsyncSessionLocal() as db:
        job = await db.get(Job, job_id)
        job.status = JobStatus.COMPLETE.value
        job.completed_at = datetime.utcnow()
        for f in findings:
            source = f.get("source", "")
            if isinstance(source, list):
                source = ",".join(source)
            db.add(Finding(
                job_id=job_id,
                type=f.get("type", ""),
                severity=f.get("severity", ""),
                file=f.get("file", ""),
                line=f.get("line"),
                message=f.get("message", ""),
                suggestion=f.get("suggestion"),
                source=source,
            ))
        await db.commit()


async def _fail_job(job_id: str):
    async with AsyncSessionLocal() as db:
        job = await db.get(Job, job_id)
        if job:
            job.status = JobStatus.FAILED.value
            await db.commit()



@shared_task(bind=True, name="workers.tasks.run_review", max_retries=3)
def run_review(
    self,
    job_id: str,
    diff: str | None = None,
    diff_url: str | None = None,
    content: str | None = None,
    filename: str | None = None,
    repo: str | None = None,
    commit_sha: str | None = None,
    pull_number: int | None = None,
    **kwargs,
):
    log = logger.bind(job_id=job_id, repo=repo, commit_sha=commit_sha, pull_number=pull_number)
    log.info("task.started")

    asyncio.run(_create_job(job_id, repo, commit_sha, pull_number))

    try:
        check_run_id = None
        if repo and commit_sha:
            try:
                check_run_id = create_check_run(repo, commit_sha)
                log.info("task.check_run_created", check_run_id=check_run_id)
            except Exception as e:
                log.warning("task.create_check_run_failed", error=str(e))

        if diff_url and not diff:
            log.info("task.fetching_diff", diff_url=diff_url)
            diff = fetch_diff(diff_url)
            log.info("task.diff_fetched", bytes_length=len(diff))

        if diff:
            parsed_files = parse_diff(diff)
        elif content and filename:
            parsed_files = [
                {
                    "filename": filename,
                    "content": content,
                    "changed_lines": list(range(1, content.count("\n") + 2)),
                }
            ]
        else:
            raise ValueError("Either diff/diff_url or content+filename must be provided")

        log.info("task.parsed_files", file_count=len(parsed_files))

        ruff_findings = []
        bandit_findings = []
        semgrep_findings = []

        for file in parsed_files:
            ruff_findings += run_ruff(file["filename"], file["content"], file["changed_lines"])
            bandit_findings += run_bandit(file["filename"], file["content"], file["changed_lines"])
            semgrep_findings += run_semgrep(file["filename"], file["content"], file["changed_lines"])

        log.info(
            "task.static_analysis_done",
            ruff=len(ruff_findings),
            bandit=len(bandit_findings),
            semgrep=len(semgrep_findings),
        )

        try:
            llm_findings = run_llm_review(parsed_files)
            log.info("task.llm_review_done", llm_findings=len(llm_findings))
        except Exception as e:
            log.error("task.llm_review_failed", error=str(e), exc_info=True)
            llm_findings = []

        result = aggregate_findings(ruff_findings, bandit_findings, semgrep_findings, llm_findings)
        findings = result.get("findings", [])
        summary = result.get("summary", {})
        total = result.get("total", 0)

        log.info("task.aggregated_results", total_findings=total, summary=summary)

        if repo and commit_sha and check_run_id:
            try:
                conclusion = "failure" if summary.get("critical") or summary.get("high") else "success"
                summary_text = "\n".join(f"{k}: {v}" for k, v in summary.items())
                complete_check_run(repo, check_run_id, conclusion, summary_text)
                log.info("task.check_run_completed", check_run_id=check_run_id, conclusion=conclusion)
            except Exception as e:
                log.warning("task.complete_check_run_failed", error=str(e))

        if repo and pull_number:
            try:
                post_pr_comment(repo, pull_number, findings, summary, total)
                log.info("task.pr_comment_posted", repo=repo, pull_number=pull_number)
            except Exception as e:
                log.error("task.post_pr_comment_failed", error=str(e), exc_info=True)

        asyncio.run(_complete_job(job_id, findings))
        log.info("task.completed_successfully", job_id=job_id)
        return result

    except Exception as exc:
        log.error("task.failed_critically", error=str(exc), exc_info=True)
        asyncio.run(_fail_job(job_id))
        raise