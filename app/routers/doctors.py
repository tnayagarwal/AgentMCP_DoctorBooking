from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db import get_db
from app import models
from app.schemas import DoctorIn, DoctorOut, AvailabilityOut

router = APIRouter(prefix="/doctors", tags=["doctors"])

@router.get("", response_model=List[DoctorOut])
def list_doctors(db: Session = Depends(get_db)):
	return db.query(models.Doctor).all()

@router.post("", response_model=DoctorOut)
def create_doctor(payload: DoctorIn, db: Session = Depends(get_db)):
	d = models.Doctor(**payload.model_dump())
	db.add(d)
	db.commit()
	db.refresh(d)
	return d

@router.get("/{doctor_id}", response_model=DoctorOut)
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
	d = db.query(models.Doctor).filter(models.Doctor.doctor_id == doctor_id).first()
	if not d:
		raise HTTPException(status_code=404, detail="Doctor not found")
	return d

@router.get("/{doctor_id}/availability/{date}", response_model=List[AvailabilityOut])
def availability_for_date(doctor_id: int, date: str, db: Session = Depends(get_db)):
	rows = db.query(models.DoctorAvailability).filter(
		models.DoctorAvailability.doctor_id == doctor_id,
		models.DoctorAvailability.available_date == date,
		models.DoctorAvailability.is_booked == False,
	).all()
	return rows

