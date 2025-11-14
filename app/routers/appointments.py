from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.db import get_db
from app import models
from app.schemas import AppointmentOut
from app.services.booking import book_slot
from app.integrations.notifications import send_email, send_email_with_attachment, whatsapp_send_text
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
	location: str | None = Body(None),
	db: Session = Depends(get_db),
):
	try:
		appt = book_slot(db, doctor_id, patient_id, date, start_time, reason)
	except ValueError as ve:
		raise HTTPException(status_code=400, detail=str(ve))

	# set visit type based on duration
	try:
		visit_type = 'returning' if (datetime.strptime(str(appt.end_time), "%H:%M:%S") - datetime.strptime(str(appt.start_time), "%H:%M:%S")).seconds == 1800 else 'new'
		appt.visit_type = visit_type
		if location:
			appt.location = location
		db.commit()
	except Exception:
		pass

	# send confirmations (best-effort)
	try:
		p = db.query(models.Patient).filter(models.Patient.patient_id == patient_id).first()
		if p and p.email:
			send_email(p.email, "Appointment Confirmation", f"Your appointment is booked for {date} at {start_time}. You'll receive the intake form after confirmation.")
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

@router.post("/{appointment_id}/forms")

def mark_forms_complete(appointment_id: int, completed: bool = Body(True), db: Session = Depends(get_db)):
	appt = db.query(models.Appointment).filter(models.Appointment.appointment_id == appointment_id).first()
	if not appt:
		raise HTTPException(status_code=404, detail="Appointment not found")
	appt.forms_completed = completed
	db.commit()
	return {"appointment_id": appointment_id, "forms_completed": appt.forms_completed}

@router.post("/{appointment_id}/confirm")

def confirm_or_cancel(appointment_id: int, confirmed: bool = Body(True), reason: str | None = Body(None), db: Session = Depends(get_db)):
	appt = db.query(models.Appointment).filter(models.Appointment.appointment_id == appointment_id).first()
	if not appt:
		raise HTTPException(status_code=404, detail="Appointment not found")
	if confirmed:
		appt.confirmation_status = 'confirmed'
		appt.cancel_reason = None
		# send intake form attachment
		try:
			p = db.query(models.Patient).filter(models.Patient.patient_id == appt.patient_id).first()
			if p and p.email:
				send_email_with_attachment(p.email, "Patient Intake Form", "Please complete this form before your appointment.", "New Patient Intake Form.pdf")
		except Exception:
			pass
	else:
		appt.confirmation_status = 'cancelled'
		appt.cancel_reason = reason
	db.commit()
	return {"appointment_id": appointment_id, "confirmation_status": appt.confirmation_status, "cancel_reason": appt.cancel_reason}
