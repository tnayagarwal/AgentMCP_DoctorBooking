from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import date, time, datetime

class InsuranceIn(BaseModel):
	carrier: str
	member_id: str
	group_number: Optional[str] = None
	payer_phone: Optional[str] = None

class InsuranceOut(InsuranceIn):
	insurance_id: int
	eligibility_status: Optional[str] = None
	last_verified_at: Optional[datetime] = None

	class Config:
		from_attributes = True

class PatientIn(BaseModel):
	name: str
	email: Optional[EmailStr] = None
	phone: Optional[str] = None
	date_of_birth: Optional[date] = None
	insurance: Optional[InsuranceIn] = None

class PatientOut(BaseModel):
	patient_id: int
	name: str
	email: Optional[EmailStr] = None
	phone: Optional[str] = None
	date_of_birth: Optional[date] = None
	insurance: Optional[InsuranceOut] = None

	class Config:
		from_attributes = True

class DoctorIn(BaseModel):
	name: str
	specialization: Optional[str] = None
	email: Optional[EmailStr] = None
	phone: Optional[str] = None

class DoctorOut(DoctorIn):
	doctor_id: int

	class Config:
		from_attributes = True

class AvailabilityOut(BaseModel):
	availability_id: int
	available_date: date
	start_time: time
	end_time: time
	is_booked: bool

	class Config:
		from_attributes = True

class AppointmentIn(BaseModel):
	doctor_id: int
	patient_id: int
	appointment_date: date
	start_time: time
	end_time: time
	reason: Optional[str] = None
	location: Optional[str] = None
	visit_type: Optional[str] = None

class AppointmentOut(AppointmentIn):
	appointment_id: int
	status: str
	forms_completed: bool | None = None
	confirmation_status: Optional[str] = None
	cancel_reason: Optional[str] = None
	created_at: datetime

	class Config:
		from_attributes = True

class ReportOut(BaseModel):
	report_id: int
	appointment_id: int
	symptoms: Optional[str] = None
	diagnosis: Optional[str] = None
	created_at: datetime

	class Config:
		from_attributes = True

class BookingRequest(BaseModel):
	patient_email: Optional[EmailStr] = None
	patient_id: Optional[int] = None
	doctor_name: Optional[str] = None
	doctor_id: Optional[int] = None
	date: str
	start_time: str
	reason: Optional[str] = None

