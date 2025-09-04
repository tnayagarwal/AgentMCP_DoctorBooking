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
	for a in rows:
		data.append({
			"appointment_id": a.appointment_id,
			"doctor_id": a.doctor_id,
			"patient_id": a.patient_id,
			"date": a.appointment_date,
			"start_time": a.start_time,
			"end_time": a.end_time,
			"status": a.status,
			"reason": a.reason,
		})
	df = pd.DataFrame(data)
	output = BytesIO()
	df.to_excel(output, index=False)
	output.seek(0)
	fname = f"appointments_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
	return StreamingResponse(output, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={"Content-Disposition": f"attachment; filename={fname}"})

