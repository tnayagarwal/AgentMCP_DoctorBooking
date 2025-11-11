from sqlalchemy import Column, Integer, String, Date, Time, Boolean, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from app.db import Base

class Doctor(Base):
	__tablename__ = "doctors"
	doctor_id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	specialization = Column(String)
	email = Column(String)
	phone = Column(String)
	created_at = Column(DateTime, server_default=func.now())

	availabilities = relationship("DoctorAvailability", back_populates="doctor")
	appointments = relationship("Appointment", back_populates="doctor")

class Patient(Base):
	__tablename__ = "patients"
	patient_id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	email = Column(String, unique=False)
	phone = Column(String)
	date_of_birth = Column(Date)
	created_at = Column(DateTime, server_default=func.now())

	insurance = relationship("Insurance", back_populates="patient", uselist=False)
	appointments = relationship("Appointment", back_populates="patient")

class Insurance(Base):
	__tablename__ = "insurance"
	insurance_id = Column(Integer, primary_key=True)
	patient_id = Column(Integer, ForeignKey("patients.patient_id"), nullable=False)
	carrier = Column(String, nullable=False)
	member_id = Column(String, nullable=False)
	group_number = Column(String)
	payer_phone = Column(String)
	eligibility_status = Column(String)
	last_verified_at = Column(DateTime)

	patient = relationship("Patient", back_populates="insurance")

class DoctorAvailability(Base):
	__tablename__ = "doctor_availability"
	availability_id = Column(Integer, primary_key=True)
	doctor_id = Column(Integer, ForeignKey("doctors.doctor_id"), nullable=False)
	available_date = Column(Date, nullable=False)
	start_time = Column(Time, nullable=False)
	end_time = Column(Time, nullable=False)
	is_booked = Column(Boolean, default=False)

	doctor = relationship("Doctor", back_populates="availabilities")

class Appointment(Base):
	__tablename__ = "appointments"
	appointment_id = Column(Integer, primary_key=True)
	doctor_id = Column(Integer, ForeignKey("doctors.doctor_id"), nullable=False)
	patient_id = Column(Integer, ForeignKey("patients.patient_id"), nullable=False)
	appointment_date = Column(Date, nullable=False)
	start_time = Column(Time, nullable=False)
	end_time = Column(Time, nullable=False)
	reason = Column(Text)
	status = Column(String, default="Scheduled")
	created_at = Column(DateTime, server_default=func.now())

	doctor = relationship("Doctor", back_populates="appointments")
	patient = relationship("Patient", back_populates="appointments")
	report = relationship("PatientReport", back_populates="appointment", uselist=False)

class PatientReport(Base):
	__tablename__ = "patient_reports"
	report_id = Column(Integer, primary_key=True)
	appointment_id = Column(Integer, ForeignKey("appointments.appointment_id"), nullable=False)
	symptoms = Column(Text)
	diagnosis = Column(Text)
	created_at = Column(DateTime, server_default=func.now())

	appointment = relationship("Appointment", back_populates="report")

