from celery import Celery
from app.config import settings

celery_app = Celery(
	"clinic",
	broker=settings.celery_broker_url,
	backend=settings.celery_result_backend,
)

@celery_app.task

def send_reminder_task(channel: str, to_value: str | None, message: str) -> dict:
	# Here you could call real providers; keep it simple
	return {"status": "queued", "channel": channel, "to": to_value, "message": message[:160]}

