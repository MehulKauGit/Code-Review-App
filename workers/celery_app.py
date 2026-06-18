from celery import Celery
from api.config import settings

celery_app=Celery("code_reivew",broker=settings.redis_url,backend=settings.redis_url)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_routes={
        "workers.tasks.run_review":{"queue":"parse"},
    },
    )