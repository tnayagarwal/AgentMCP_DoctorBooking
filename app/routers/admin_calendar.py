from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.responses import PlainTextResponse
from app.db import get_db
from app import models
from app.services.calendar_files import create_ics

router = APIRouter(prefix="/calendar", tags=["calendar"])

@router.get("/appointment/{appointment_id}.ics")

def export_ics(appointment_id: int, db: Session = Depends(get_db)):
	appt = db.query(models.Appointment).filter(models.Appointment.appointment_id == appointment_id).first()
	if not appt:
		raise HTTPException(status_code=404, detail="Appointment not found")
	start_iso = f"{appt.appointment_date}T{appt.start_time}"
	end_iso = f"{appt.appointment_date}T{appt.end_time}"
	ics = create_ics(f"Appointment with Doctor {appt.doctor_id}", start_iso, end_iso)
	return PlainTextResponse(content=ics, media_type='text/calendar')
