from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.db import get_db
from app import models
from app.integrations.notifications import send_email, whatsapp_send_text

router = APIRouter(prefix="/reschedule", tags=["reschedule"])

@router.post("/day")

def reschedule_day(
	doctor_id: int = Body(...),
	from_date: str = Body(...),
	to_date: str = Body(...),
	notify: bool = Body(True),
	db: Session = Depends(get_db),
):
	try:
		d_from = datetime.strptime(from_date, "%Y-%m-%d").date()
		d_to = datetime.strptime(to_date, "%Y-%m-%d").date()
	except Exception:
		raise HTTPException(status_code=400, detail="Invalid dates")
	appts = db.query(models.Appointment).filter(models.Appointment.doctor_id == doctor_id, models.Appointment.appointment_date == d_from).all()
	if not appts:
		return {"updated": 0}
	count = 0
	for a in appts:
		# free old
		old = db.query(models.DoctorAvailability).filter(models.DoctorAvailability.doctor_id == doctor_id, models.DoctorAvailability.available_date == d_from, models.DoctorAvailability.start_time == a.start_time, models.DoctorAvailability.end_time == a.end_time).first()
		if old:
			old.is_booked = False
		# ensure new
		new = db.query(models.DoctorAvailability).filter(models.DoctorAvailability.doctor_id == doctor_id, models.DoctorAvailability.available_date == d_to, models.DoctorAvailability.start_time == a.start_time, models.DoctorAvailability.end_time == a.end_time).first()
		if not new:
			new = models.DoctorAvailability(doctor_id=doctor_id, available_date=d_to, start_time=a.start_time, end_time=a.end_time, is_booked=True)
			db.add(new)
		else:
			new.is_booked = True
		a.appointment_date = d_to
		a.status = 'Rescheduled'
		count += 1
		if notify:
			p = db.query(models.Patient).filter(models.Patient.patient_id == a.patient_id).first()
			try:
				if p and p.email:
					send_email(p.email, "Appointment Rescheduled", f"Your appointment has been moved to {to_date} at {a.start_time}.")
				if p and p.phone:
					whatsapp_send_text(f"Your appointment has been moved to {to_date} at {a.start_time}.")
			except Exception:
				pass
	db.commit()
	return {"updated": count}
