from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db import engine, Base
from app.routers import doctors, patients, appointments, admin
from app.routers import nlp, reminders
from app.routers import insurance
from app.routers import admin_calendar

app = FastAPI(title="Clinic Scheduling API", version="1.0.0")

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# Create tables on startup for quick demo; in production use Alembic
Base.metadata.create_all(bind=engine)

app.include_router(doctors.router)
app.include_router(patients.router)
app.include_router(appointments.router)
app.include_router(admin.router)
app.include_router(nlp.router)
app.include_router(reminders.router)
app.include_router(insurance.router)
app.include_router(admin_calendar.router)

@app.get("/")

def root():
	return {"status": "ok", "env": settings.app_env}
