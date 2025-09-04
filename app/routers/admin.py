from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app import models
import pandas as pd
from io import BytesIO
from fastapi.responses import StreamingResponse
from datetime import datetime

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/export/appointments.xlsx")

def export_appointments(db: Session = Depends(get_db)):
	rows = db.query(models.Appointment).all()
	data = []
	# prefetch patients + insurance
	patients = {p.patient_id: p for p in db.query(models.Patient).all()}
	ins_map = {i.patient_id: i for i in db.query(models.Insurance).all()}
	for a in rows:
		p = patients.get(a.patient_id)
		i = ins_map.get(a.patient_id)
		data.append({
			"appointment_id": a.appointment_id,
			"doctor_id": a.doctor_id,
			"patient_id": a.patient_id,
			"patient_email": p.email if p else None,
			"date": a.appointment_date,
			"start_time": a.start_time,
			"end_time": a.end_time,
			"status": a.status,
			"visit_type": a.visit_type,
			"location": a.location,
			"forms_completed": a.forms_completed,
			"confirmation_status": a.confirmation_status,
			"cancel_reason": a.cancel_reason,
			"carrier": i.carrier if i else None,
			"member_id": i.member_id if i else None,
			"group_number": i.group_number if i else None,
		})
	df = pd.DataFrame(data)
	output = BytesIO()
	df.to_excel(output, index=False)
	output.seek(0)
	fname = f"appointments_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
	return StreamingResponse(output, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={"Content-Disposition": f"attachment; filename={fname}"})

