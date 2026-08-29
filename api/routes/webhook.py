import hashlib
import hmac
from fastapi import HTTPException

import uuid
import structlog
from fastapi import APIRouter,Header,Request
from api.models.webhook import PullRequestEvent, SUPPORTED_PR_ACTIONS
from api.config import settings
from workers.tasks import run_review

def verify_github_signature(payload:bytes,sig_header:str | None)->None:
    if not sig_header:
        raise HTTPException(status_code=401,detail="Missing signature header.")
    
    if not sig_header.startswith("sha256="):
        raise HTTPException(status_code=401,detail="Malformed signature.")
    
    expected=hmac.new(
        settings.github_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    received =sig_header[len("sha256="):]
    if not hmac.compare_digest(expected,received):
        raise HTTPException(status_code=401, detail="Invalid signature.")
    

logger = structlog.get_logger()
router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("", status_code=202)
@router.post("/", status_code=202)
@router.post("/github", status_code=202)
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(None),
    x_hub_signature_256: str | None = Header(None),
    x_github_delivery: str | None = Header(None),
) -> dict:


    raw_body = await request.body()
    # step 1 - verify before anything else
    verify_github_signature(raw_body, x_hub_signature_256)

    log = logger.bind(event=x_github_event, delivery=x_github_delivery)


    # step 2 - filter event type
    if x_github_event == "ping":
        log.info("webhook.ping_received")
        return {"status": "ok", "message": "pong"}

    if x_github_event != "pull_request":
        log.info("webhook.ignored", reason=f"unsupported event: {x_github_event}")
        return {"status": "ignored", "reason": f"event '{x_github_event}' not handled"}

    
    #step 3 - parse payload
    try:
        event=PullRequestEvent.model_validate_json(raw_body)
    except Exception as exc:
        log.warning("webhook.parse_error",error=str(exc))
        raise HTTPException(status_code=422,detail="Could not parase payload.")
    
    #step 4 - filter PR action
    if event.action not in SUPPORTED_PR_ACTIONS:
        log.info("webhook.ignored",reason=f"action'{event.action}'skipped")
        return {"status":"ignored","reason":f"action '{event.action}' skipped"}
    
    #step 5 - queue the job
    job_id=str(uuid.uuid4())
    run_review.apply_async(
        kwargs={
            "job_id":job_id,
            "diff_url":event.pull_request.diff_url,
            "repo":event.repository.full_name,
            "commit_sha":event.pull_request.head.sha,
            "pull_number":event.number,  
        },
        task_id=job_id,
    )
    log.info("webhook.queued",job_id=job_id,repo=event.repository.full_name)
    return  {"status":"queued","job_id":job_id}

