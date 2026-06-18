import uuid
from fastapi import APIRouter

from api.models.review import ReviewRequest, ReviewResponse, JobStatus
from workers.tasks import run_review

from celery.result import AsyncResult
from workers.celery_app import celery_app
from api.models.review import ReviewResult

router=APIRouter(prefix="/review",tags=["review"])

@router.post("",response_model=ReviewResponse,status_code=202)

async def submit_review(payload:ReviewRequest)-> ReviewResponse:
    job_id =str(uuid.uuid4())
    run_review.apply_async(
        kwargs={
            "job_id":job_id,
            "diff":payload.diff,
            "content":payload.content,
            "filename":payload.filename,
            "repo":payload.repo,
            "commit_sha":payload.commit_sha,
        },
        task_id=job_id,
    )
    return ReviewResponse(job_id=job_id)

@router.get("/{job_id}",response_model=ReviewResult)

async def get_review(job_id:str)->ReviewResult:
    result =AsyncResult(job_id,app=celery_app)
    
    if result.state=="PENDING":
        return ReviewResult(job_id=job_id,status=JobStatus.QUEUED)
    
    if result.state=="STARTED":
        return ReviewResult(job_id=job_id,status=JobStatus.RUNNING)
    
    if result.state=="FAILURE":
        return ReviewResult(job_id=job_id,status=JobStatus.FAILED,error=str(result.result))
    
    if result.state=="SUCCESS":
        data=result.result or {}
        return ReviewResult(
            job_id=job_id,
            status=JobStatus.COMPLETE,
            findings=data.get("findings",[]),
            summary=data.get("summary",{}),
        )