from celery import Celery # type: ignore
from app.core.config import settings

celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.services.converter"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],  
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=1, 
    worker_prefetch_multiplier=1,
)
