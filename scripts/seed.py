from app.db import SessionLocal, Base, engine
from app import models
from datetime import date, time, timedelta, datetime

Base.metadata.create_all(bind=engine)

def seed():
	db = SessionLocal()
	if db.query(models.Doctor).count() == 0:
		docs = [
			models.Doctor(name="Dr. Ahuja", specialization="General", email="ahuja@example.com", phone="+911234567890"),
			models.Doctor(name="Dr. Mehra", specialization="Pediatrics", email="mehra@example.com", phone="+919876543210"),
		]
		db.add_all(docs)
		db.commit()
	if db.query(models.Patient).count() == 0:
		patients = []
		for i in range(1, 51):
			patients.append(models.Patient(name=f"Patient {i}", email=f"patient{i}@example.com", phone=f"+9100000{i:04d}"))
		db.add_all(patients)
		db.commit()
	# availability next 5 days
	if db.query(models.DoctorAvailability).count() == 0:
		all_docs = db.query(models.Doctor).all()
		start = datetime.utcnow().date()
		for d in all_docs:
			for day in range(0, 5):
				dt = start + timedelta(days=day)
				for hh in [9, 9, 10, 11, 14, 15, 16]:
					st = f"{hh:02d}:00:00"; et = f"{hh:02d}:30:00"
					db.add(models.DoctorAvailability(doctor_id=d.doctor_id, available_date=dt, start_time=st, end_time=et, is_booked=False))
		db.commit()
	db.close()

if __name__ == "__main__":
	seed()
	print("Seeded sample data.")

