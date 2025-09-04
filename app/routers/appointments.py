from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.db import get_db
from app import models
from app.schemas import AppointmentOut
from app.services.booking import book_slot
from app.integrations.notifications import send_email, whatsapp_send_text
from app.workers.celery_app import send_reminder_task
from datetime import datetime

router = APIRouter(prefix="/appointments", tags=["appointments"])

@router.post("/book", response_model=AppointmentOut)
def book(
	doctor_id: int = Body(...),
	patient_id: int = Body(...),
	date: str = Body(...),
	start_time: str = Body(...),
	reason: str | None = Body(None),
	db: Session = Depends(get_db),
):
	try:
		appt = book_slot(db, doctor_id, patient_id, date, start_time, reason)
	except ValueError as ve:
		raise HTTPException(status_code=400, detail=str(ve))

	# send confirmations (best-effort)
	try:
		p = db.query(models.Patient).filter(models.Patient.patient_id == patient_id).first()
		if p and p.email:
			send_email(p.email, "Appointment Confirmation", f"Your appointment is booked for {date} at {start_time}. Please fill the attached intake form before your visit.")
		if p and p.phone:
			whatsapp_send_text(f"Appointment booked for {date} at {start_time}. Reply YES to confirm.")
		# schedule 3 reminders (immediate queue for demo)
		appt_dt = datetime.fromisoformat(f"{date}T{start_time if len(start_time.split(':'))==3 else start_time+':00'}")
		for hours in (48, 24, 2):
			msg = f"Reminder: Appointment at {appt_dt.isoformat()}"
			send_reminder_task.delay("whatsapp", p.phone if p else None, msg)
			send_reminder_task.delay("email", p.email if p else None, msg)
	except Exception:
		pass

	return appt
