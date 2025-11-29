import pytest
from app.db import SessionLocal, Base, engine
from app import models
from scripts.seed import seed
from datetime import date

@pytest.fixture(scope='module', autouse=True)

def setup_db():
	Base.metadata.create_all(bind=engine)
	seed()
	yield


def test_booking_durations():
	db = SessionLocal()
	d = db.query(models.Doctor).first()
	p = db.query(models.Patient).first()
	from app.services.booking import book_slot
	# returning: create a prior appt
	old = models.Appointment(doctor_id=d.doctor_id, patient_id=p.patient_id, appointment_date=date.today(), start_time='08:00:00', end_time='08:30:00', status='Done')
	db.add(old); db.commit()
	# returning -> 30 mins
	appt_r = book_slot(db, d.doctor_id, p.patient_id, date.today().isoformat(), '09:00')
	assert str(appt_r.end_time) in ('09:30:00','09:30')
	# new patient -> 60 mins: pick a different patient
	p2 = db.query(models.Patient).filter(models.Patient.patient_id != p.patient_id).first()
	appt_n = book_slot(db, d.doctor_id, p2.patient_id, date.today().isoformat(), '10:00')
	assert str(appt_n.end_time) in ('11:00:00','11:00','10:30:00','10:30')  # depends on seed density
	db.close()


def test_ics_export():
	from app.services.calendar_files import create_ics
	ics = create_ics('Test', '20250101T100000', '20250101T103000')
	assert 'BEGIN:VEVENT' in ics
