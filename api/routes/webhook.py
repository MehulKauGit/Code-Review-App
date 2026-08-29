import hashlib
import hmac
import json
import uuid
from fastapi import HTTPException

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

    # step 3 - handle check_suite / check_run re-request events
    if x_github_event in ("check_suite", "check_run"):
        try:
            payload = json.loads(raw_body)
            action = payload.get("action", "")
            if action in ("requested", "rerequested"):
                check_obj = payload.get("check_suite") or payload.get("check_run", {}).get("check_suite", {})
                pull_requests = check_obj.get("pull_requests", [])
                repo_full_name = payload.get("repository", {}).get("full_name", "")
                head_sha = check_obj.get("head_sha") or payload.get("check_run", {}).get("head_sha", "")

                if pull_requests and repo_full_name and head_sha:
                    pr = pull_requests[0]
                    pr_number = pr.get("number")
                    diff_url = f"https://github.com/{repo_full_name}/pull/{pr_number}.diff"
                    job_id = str(uuid.uuid4())
                    run_review.apply_async(
                        kwargs={
                            "job_id": job_id,
                            "diff_url": diff_url,
                            "repo": repo_full_name,
                            "commit_sha": head_sha,
                            "pull_number": pr_number,
                        },
                        task_id=job_id,
                    )
                    log.info("webhook.check_suite.queued", job_id=job_id, repo=repo_full_name, pr=pr_number)
                    return {"status": "queued", "job_id": job_id, "event": x_github_event}

            log.info("webhook.check_suite.ignored", action=action)
            return {"status": "ignored", "reason": f"{x_github_event} action '{action}' skipped"}
        except Exception as exc:
            log.warning("webhook.check_suite_error", error=str(exc))
            return {"status": "ignored", "reason": f"could not process {x_github_event}"}

    if x_github_event != "pull_request":
        log.info("webhook.ignored", reason=f"unsupported event: {x_github_event}")
        return {"status": "ignored", "reason": f"event '{x_github_event}' not handled"}

    # step 4 - parse pull_request payload
    try:
        event = PullRequestEvent.model_validate_json(raw_body)
    except Exception as exc:
        log.warning("webhook.parse_error", error=str(exc))
        raise HTTPException(status_code=422, detail="Could not parse payload.")

    # step 5 - filter PR action
    if event.action not in SUPPORTED_PR_ACTIONS:
        log.info("webhook.ignored", reason=f"action '{event.action}' skipped")
        return {"status": "ignored", "reason": f"action '{event.action}' skipped"}

    # step 6 - queue the review job
    job_id = str(uuid.uuid4())
    run_review.apply_async(
        kwargs={
            "job_id": job_id,
            "diff_url": event.pull_request.diff_url,
            "repo": event.repository.full_name,
            "commit_sha": event.pull_request.head.sha,
            "pull_number": event.number,
        },
        task_id=job_id,
    )
    log.info("webhook.queued", job_id=job_id, repo=event.repository.full_name)
    return {"status": "queued", "job_id": job_id}


