from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.db import get_db
from app import models
from app.schemas import InsuranceIn, InsuranceOut

router = APIRouter(prefix="/insurance", tags=["insurance"])

@router.get("/{patient_id}", response_model=InsuranceOut)

def get_insurance(patient_id: int, db: Session = Depends(get_db)):
	ins = db.query(models.Insurance).filter(models.Insurance.patient_id == patient_id).first()
	if not ins:
		raise HTTPException(status_code=404, detail="Insurance not found")
	return ins

@router.post("/{patient_id}", response_model=InsuranceOut)

def set_insurance(patient_id: int, payload: InsuranceIn, db: Session = Depends(get_db)):
	pat = db.query(models.Patient).filter(models.Patient.patient_id == patient_id).first()
	if not pat:
		raise HTTPException(status_code=404, detail="Patient not found")
	ins = db.query(models.Insurance).filter(models.Insurance.patient_id == patient_id).first()
	if not ins:
		ins = models.Insurance(patient_id=patient_id, **payload.model_dump())
		db.add(ins)
	else:
		for k, v in payload.model_dump().items():
			setattr(ins, k, v)
	db.commit(); db.refresh(ins)
	return ins
