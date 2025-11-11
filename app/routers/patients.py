from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db import get_db
from app import models
from app.schemas import PatientIn, PatientOut
from sqlalchemy.sql import func as sa_func

router = APIRouter(prefix="/patients", tags=["patients"])

@router.get("", response_model=List[PatientOut])
def list_patients(db: Session = Depends(get_db)):
	return db.query(models.Patient).all()

@router.post("", response_model=PatientOut)
def create_patient(payload: PatientIn, db: Session = Depends(get_db)):
	patient = models.Patient(
		name=payload.name,
		email=payload.email,
		phone=payload.phone,
		date_of_birth=payload.date_of_birth,
	)
	db.add(patient)
	db.flush()
	if payload.insurance:
		ins = models.Insurance(
			patient_id=patient.patient_id,
			carrier=payload.insurance.carrier,
			member_id=payload.insurance.member_id,
			group_number=payload.insurance.group_number,
			payer_phone=payload.insurance.payer_phone,
		)
		db.add(ins)
	db.commit()
	db.refresh(patient)
	return patient

@router.get("/lookup/by_email/{email}")
def get_patient_id_by_email(email: str, db: Session = Depends(get_db)):
	p = db.query(models.Patient).filter(sa_func.lower(models.Patient.email) == email.lower()).first()
	if not p:
		raise HTTPException(status_code=404, detail="Patient not found")
	return {"patient_id": p.patient_id}

