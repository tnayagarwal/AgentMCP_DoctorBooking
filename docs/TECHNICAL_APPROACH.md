# Technical Approach

## Architecture Overview
- FastAPI backend with modular routers (`doctors`, `patients`, `appointments`, `insurance`, `nlp`, `admin`, `calendar`, `intake`, `reminders`, `analytics`, `reschedule`).
- SQLAlchemy ORM models for `Doctor`, `Patient`, `Insurance`, `DoctorAvailability`, `Appointment`, `PatientReport` (extensible).
- Services layer for booking logic (60/30 mins), calendar ICS, notifications (email/WhatsApp), and data seeding.
- Optional Celery workers for reminders; fallback to inline queuing in demo.
- Streamlit demo UI for parse, availability browsing, and booking.

## Framework Choice
- FastAPI for robust, async-friendly API surface and Pydantic validation.
- LangChain + Groq (llama3) for NLP parsing with resilient JSON extraction.
- SQLAlchemy for ORM portability; SQLite for demo, Postgres compatible in prod.

## Integration Strategy
- Email via Gmail API if token is present; otherwise skipped (return False).
- WhatsApp Cloud API with template fallback; skipped if tokens missing.
- Calendar simulated via ICS export endpoint (`/calendar/appointment/{id}.ics`).
- Reminders via Celery task skeleton or inline dispatch for demo.

## Challenges & Solutions
- Natural language date/time: normalization helpers for ambiguous inputs.
- New vs returning duration: consecutive slot verification for 60-min new visits.
- Double-book/overlap: availability table used as single source-of-truth; booking flips `is_booked` flags.
- External failures: best-effort try/except with structured logging and user-visible status codes.
- Data: synthetic generator + idempotent seeding from CSVs.

## Testing
- Core tests for booking durations and ICS creation; extend with more coverage as needed.

## Security & Ops
- Env-driven config (`env.sample`); never commit secrets.
- Dockerfile and docker-compose for local orchestration.
- Global exception handler with structured logs.
