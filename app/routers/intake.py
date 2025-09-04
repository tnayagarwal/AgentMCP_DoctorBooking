from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.db import get_db
from app import models

router = APIRouter(prefix="/intake", tags=["intake"])

@router.post("/start")

def intake_start(
	name: str = Body(...),
	email: str | None = Body(None),
	phone: str | None = Body(None),
	dob: str | None = Body(None),
	doctor_name: str | None = Body(None),
	location: str | None = Body(None),
	db: Session = Depends(get_db),
):
	# upsert patient
	p = None
	if email:
		p = db.query(models.Patient).filter(models.Patient.email == email).first()
	if not p:
		p = models.Patient(name=name, email=email, phone=phone)
		try:
			if dob:
				p.date_of_birth = datetime.strptime(dob, "%Y-%m-%d").date()
		except Exception:
			pass
		db.add(p)
		db.commit(); db.refresh(p)
	# match doctor
	did = None
	if doctor_name:
		d = db.query(models.Doctor).filter(models.Doctor.name.ilike(f"%{doctor_name}%")).first()
		did = d.doctor_id if d else None
	return {"patient_id": p.patient_id, "doctor_id": did, "location": location}
