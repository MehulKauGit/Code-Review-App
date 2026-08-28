import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.limiter import RateLimiter
from api.models.review import ReviewRequest, ReviewResponse, JobStatus
from api.models.review import ReviewResult
from api.deps import get_db, verify_api_key
from api.models.db import Job, Finding
from workers.tasks import run_review

router = APIRouter(prefix="/review", tags=["review"], dependencies=[Depends(verify_api_key)])
review_limiter = RateLimiter(
    times=settings.rate_limit_review_max,
    seconds=settings.rate_limit_review_window_seconds,
)


@router.post("", response_model=ReviewResponse, status_code=202, dependencies=[Depends(review_limiter)])
async def submit_review(payload: ReviewRequest, db: AsyncSession = Depends(get_db)) -> ReviewResponse:

    # Idempotency: same commit_sha with a completed job -> return cached job_id
    if payload.commit_sha:
        result = await db.execute(
            select(Job).where(
                Job.commit_sha == payload.commit_sha,
                Job.status == "complete",
            ).order_by(Job.created_at.desc())
        )
        existing = result.scalars().first()
        if existing:
            return ReviewResponse(job_id=existing.id)

    job_id = str(uuid.uuid4())
    run_review.apply_async(
        kwargs={
            "job_id": job_id,
            "diff": payload.diff,
            "content": payload.content,
            "filename": payload.filename,
            "repo": payload.repo,
            "commit_sha": payload.commit_sha,
        },
        task_id=job_id,
    )
    return ReviewResponse(job_id=job_id)


@router.get("/history")
async def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size

    result = await db.execute(
        select(Job).order_by(Job.created_at.desc()).offset(offset).limit(page_size)
    )
    jobs = result.scalars().all()

    items = []
    for job in jobs:
        count_result = await db.execute(
            select(Finding).where(Finding.job_id == job.id)
        )
        finding_count = len(count_result.scalars().all())
        items.append({
            "job_id": job.id,
            "repo": job.repo,
            "commit_sha": job.commit_sha,
            "status": job.status,
            "created_at": job.created_at,
            "completed_at": job.completed_at,
            "finding_count": finding_count,
        })

    return {"page": page, "page_size": page_size, "items": items}


@router.get("/{job_id}", response_model=ReviewResult)
async def get_review(job_id: str, db: AsyncSession = Depends(get_db)) -> ReviewResult:
    job = await db.get(Job, job_id)

    if job is None:
        return ReviewResult(job_id=job_id, status=JobStatus.QUEUED)

    if job.status == "running":
        return ReviewResult(job_id=job_id, status=JobStatus.RUNNING)

    if job.status == "failed":
        return ReviewResult(job_id=job_id, status=JobStatus.FAILED, error="Job failed")

    if job.status == "complete":
        result = await db.execute(select(Finding).where(Finding.job_id == job_id))
        findings = result.scalars().all()
        findings_data = [
            {
                "type": f.type,
                "severity": f.severity,
                "file": f.file,
                "line": f.line,
                "message": f.message,
                "suggestion": f.suggestion,
                "source": f.source,
            }
            for f in findings
        ]
        summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for f in findings:
            if f.severity in summary:
                summary[f.severity] += 1

        return ReviewResult(job_id=job_id, status=JobStatus.COMPLETE, findings=findings_data, summary=summary)

    return ReviewResult(job_id=job_id, status=JobStatus.QUEUED)