import structlog
from celery import shared_task

logger=structlog.get_logger()

@shared_task(name="wokers.tasks.run_review",bind=True,max_retries=3)

def run_review(self,job_id:str,**kwargs)->dict:
    log=logger.bind(job_id=job_id)
    log.info("task.run_review.started")
    #Phase 2 fills this in 
    return {"findings":[],"summary":{"total":0}} 