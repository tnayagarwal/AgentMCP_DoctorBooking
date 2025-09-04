from fastapi import APIRouter, Body
from datetime import datetime, timedelta
from app.workers.celery_app import send_reminder_task

router = APIRouter(prefix="/reminders", tags=["reminders"])

@router.post("/schedule")
def schedule_reminders(
	channel: str = Body("email"),
	to_value: str = Body(...),
	appointment_datetime: str = Body(...),
):
	# Schedule 3 reminders: 48h, 24h, and 2h before
	when = datetime.fromisoformat(appointment_datetime)
	for hours in (48, 24, 2):
		msg = f"Reminder: Appointment at {when.isoformat()}"
		# In real deployment, use Celery ETAs/beat; here just enqueue immediate for demo
		send_reminder_task.delay(channel, to_value, msg)
	return {"scheduled": 3}

@router.post("/webhook")

def webhook_reply(payload: dict = Body(...)):
	# Example payload: { appointment_id, patient_id, answered: { forms_filled: bool, confirmed: bool, cancel_reason?: str } }
	return {"status": "received", "payload": payload}

