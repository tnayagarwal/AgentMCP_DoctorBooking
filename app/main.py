from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db import engine, Base
from app.routers import doctors, patients, appointments, admin
from app.routers import nlp, reminders
from app.routers import insurance
from app.routers import admin_calendar
from app.routers import intake
from app.routers import analytics
from app.routers import reschedule
from fastapi.responses import JSONResponse
from app.logger import get_logger

app = FastAPI(title="Clinic Scheduling API", version="1.0.0")
log = get_logger("api")

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
app.include_router(intake.router)
app.include_router(analytics.router)
app.include_router(reschedule.router)

@app.get("/")

def root():
	return {"status": "ok", "env": settings.app_env}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
	log.exception("Unhandled error: %s", exc)
	return JSONResponse(status_code=500, content={"detail": "Internal server error"})
