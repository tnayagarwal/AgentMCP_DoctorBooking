from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func
from app.db import get_db
from app import models

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/count")

def count_appointments(date: str, doctor_id: int | None = None, db: Session = Depends(get_db)):
	q = db.query(models.Appointment).filter(models.Appointment.appointment_date == date)
	if doctor_id:
		q = q.filter(models.Appointment.doctor_id == doctor_id)
	return {"date": date, "count": q.count()}

@router.get("/busiest")

def busiest_day(start_date: str, end_date: str, doctor_id: int | None = None, db: Session = Depends(get_db)):
	q = db.query(models.Appointment.appointment_date, sa_func.count().label("c")).filter(
		models.Appointment.appointment_date >= start_date,
		models.Appointment.appointment_date <= end_date,
	)
	if doctor_id:
		q = q.filter(models.Appointment.doctor_id == doctor_id)
	row = q.group_by(models.Appointment.appointment_date).order_by(sa_func.count().desc()).first()
	if not row:
		return {"date": None, "count": 0}
	return {"date": row[0], "count": int(row[1])}
