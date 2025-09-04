from app.db import SessionLocal, Base, engine
from app import models
from datetime import timedelta, datetime
import csv

Base.metadata.create_all(bind=engine)

def upsert_doctor(db, name: str, specialization: str = "General"):
	d = db.query(models.Doctor).filter(models.Doctor.name == name).first()
	if not d:
		d = models.Doctor(name=name, specialization=specialization)
		db.add(d); db.commit(); db.refresh(d)
	return d

def upsert_patient(db, name: str, email: str, phone: str | None = None):
	p = db.query(models.Patient).filter(models.Patient.email == email).first()
	if not p:
		p = models.Patient(name=name, email=email, phone=phone)
		db.add(p); db.commit(); db.refresh(p)
	return p

def seed():
	db = SessionLocal()
	# Seed doctors
	for nm, sp in [("Dr. Ahuja","General"),("Dr. Mehra","Pediatrics")]:
		upsert_doctor(db, nm, sp)
	# Seed patients from CSV if present
	try:
		with open('patients.csv', newline='', encoding='utf-8') as f:
			for i, row in enumerate(csv.DictReader(f)):
				upsert_patient(db, row['name'], row['email'], row.get('phone'))
	except FileNotFoundError:
		for i in range(1, 51):
			upsert_patient(db, f"Patient {i}", f"patient{i}@example.com", f"+9100000{i:04d}")
	# Seed availability from CSV if present else synthetic
	if db.query(models.DoctorAvailability).count() == 0:
		try:
			with open('schedule.csv', newline='', encoding='utf-8') as f:
				for row in csv.DictReader(f):
					d = db.query(models.Doctor).filter(models.Doctor.name == row['doctor_name']).first()
					if d:
						db.add(models.DoctorAvailability(doctor_id=d.doctor_id, available_date=row['date'], start_time=row['start_time'], end_time=row['end_time'], is_booked=False))
				db.commit()
		except FileNotFoundError:
			all_docs = db.query(models.Doctor).all()
			start = datetime.utcnow().date()
			for d in all_docs:
				for day in range(0, 5):
					dt = start + timedelta(days=day)
					for hh in (9,10,11,14,15,16):
						st = f"{hh:02d}:00:00"; et = f"{hh:02d}:30:00"
						db.add(models.DoctorAvailability(doctor_id=d.doctor_id, available_date=dt, start_time=st, end_time=et, is_booked=False))
			db.commit()
	db.close()

if __name__ == "__main__":
	seed()
	print("Seeded sample data.")

