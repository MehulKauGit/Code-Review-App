import ssl
from celery import Celery
from api.config import settings

redis_url = settings.redis_url

ssl_options = None
if redis_url.startswith("rediss://"):
    ssl_options = {"ssl_cert_reqs": ssl.CERT_NONE}

celery_app = Celery("code_review", broker=redis_url, backend=redis_url)

conf_dict = {
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "timezone": "UTC",
    "enable_utc": True,
    "task_acks_late": True,
    "task_reject_on_worker_lost": True,
    "task_routes": {
        "workers.tasks.run_review": {"queue": "parse"},
        "workers.llm.run_llm_review": {"queue": "llm"},
    },
}

if ssl_options:
    conf_dict["broker_use_ssl"] = ssl_options
    conf_dict["redis_backend_use_ssl"] = ssl_options

celery_app.conf.update(conf_dict)
celery_app.autodiscover_tasks(["workers"])

