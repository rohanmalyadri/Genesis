from celery import Celery
from celery.schedules import crontab
from app.config import settings

app = Celery(
    "genesis",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["pipeline.pagerank_job"]
)

app.conf.update(
    result_expires=3600,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Step 8 — Schedule (every 6 hours)
app.conf.beat_schedule = {
    "run-pagerank-every-6-hours": {
        "task": "pipeline.pagerank_job.run_pagerank_task",
        "schedule": crontab(minute=0, hour="*/6"),
    },
}

if __name__ == "__main__":
    app.start()
