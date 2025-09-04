from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app import models

NEW_PATIENT_MINUTES = 60
RETURNING_PATIENT_MINUTES = 30


def is_returning_patient(db: Session, patient_id: int) -> bool:
	prev = db.query(models.Appointment).filter(models.Appointment.patient_id == patient_id).first()
	return prev is not None


def compute_end_time(start_time: str, minutes: int) -> str:
	st = datetime.strptime(start_time, "%H:%M:%S" if len(start_time.split(':')) == 3 else "%H:%M")
	et = st + timedelta(minutes=minutes)
	return et.strftime("%H:%M:%S")


def book_slot(db: Session, doctor_id: int, patient_id: int, date_str: str, start_time: str, reason: str | None = None) -> models.Appointment:
	# Normalize start_time to HH:MM:SS
	start_ts = start_time if len(start_time.split(':')) == 3 else f"{start_time}:00"
	is_returning = is_returning_patient(db, patient_id)
	minutes = RETURNING_PATIENT_MINUTES if is_returning else NEW_PATIENT_MINUTES

	# First 30-min slot
	first_end = compute_end_time(start_ts, 30)
	first_slot = db.query(models.DoctorAvailability).filter(
		models.DoctorAvailability.doctor_id == doctor_id,
		models.DoctorAvailability.available_date == date_str,
		models.DoctorAvailability.start_time == start_ts,
		models.DoctorAvailability.end_time == first_end,
		models.DoctorAvailability.is_booked == False,
	).first()
	if not first_slot:
		raise ValueError("First half-hour slot not available")

	end_ts = first_end
	if minutes == 60:
		second_start = first_end
		second_end = compute_end_time(second_start, 30)
		second_slot = db.query(models.DoctorAvailability).filter(
			models.DoctorAvailability.doctor_id == doctor_id,
			models.DoctorAvailability.available_date == date_str,
			models.DoctorAvailability.start_time == second_start,
			models.DoctorAvailability.end_time == second_end,
			models.DoctorAvailability.is_booked == False,
		).first()
		if not second_slot:
			raise ValueError("Second half-hour slot not available for 60-min new patient appointment")
		first_slot.is_booked = True
		second_slot.is_booked = True
		end_ts = second_end
	else:
		first_slot.is_booked = True

	appt = models.Appointment(
		doctor_id=doctor_id,
		patient_id=patient_id,
		appointment_date=date_str,
		start_time=start_ts,
		end_time=end_ts,
		reason=reason or "General",
		status="Scheduled",
	)
	db.add(appt)
	db.commit()
	db.refresh(appt)
	return appt
