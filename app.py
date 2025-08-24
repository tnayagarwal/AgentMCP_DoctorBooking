from fastapi import FastAPI, HTTPException, Depends, Body
from sqlalchemy import create_engine, Column, Integer, String, Date, Time, Boolean, Text, ForeignKey, DateTime, func as sa_func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
from pydantic import BaseModel
import os
import json
from datetime import date, time as dt_time, datetime, timedelta
from typing import List
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import requests
from langchain_groq import ChatGroq
import re
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from langchain_core.messages import HumanMessage

# Patient agent app (lazy import to allow backend up without GROQ env)
patient_agent_app = None

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
DATABASE_URL = "xxx"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# SQLite for prompt history / notifications
HISTORY_DB = "prompt_history.db"

def init_history_db():
    conn = sqlite3.connect(HISTORY_DB)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS prompts (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, prompt TEXT, response TEXT, created_at TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, channel TEXT, message TEXT, created_at TEXT)")
    conn.commit()
    conn.close()

init_history_db()

SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/gmail.send']

def gmail_send(to_email: str, subject: str, body: str):
    try:
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        from email.mime.text import MIMEText
        import base64
        gmail = build('gmail', 'v1', credentials=creds)
        msg = MIMEText(body)
        msg['to'] = to_email
        msg['subject'] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        gmail.users().messages().send(userId='me', body={'raw': raw}).execute()
    except Exception:
        pass

def calendar_create(summary: str, start_iso: str, end_iso: str, attendee: str | None = None):
    try:
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        cal = build('calendar', 'v3', credentials=creds)
        event = {
            'summary': summary,
            'start': {'dateTime': start_iso, 'timeZone': 'UTC'},
            'end': {'dateTime': end_iso, 'timeZone': 'UTC'},
        }
        if attendee:
            event['attendees'] = [{'email': attendee}]
        cal.events().insert(calendarId='primary', body=event).execute()
    except Exception:
        pass

class AvailabilityResponse(BaseModel):
    availability_id: int
    available_date: date
    start_time: dt_time
    end_time: dt_time
    is_booked: bool

@app.get("/availability/{doctor_id}/{date}", response_model=list[AvailabilityResponse])
def get_availability(doctor_id: int, date: str, db=Depends(get_db)):
    availabilities = db.query(DoctorAvailability).filter(
        DoctorAvailability.doctor_id == doctor_id,
        DoctorAvailability.available_date == date,
        DoctorAvailability.is_booked == False
    ).all()
    return availabilities

@app.get("/doctor_id/{doctor_name}")
def get_doctor_id(doctor_name: str, db=Depends(get_db)):
    def normalize(s: str) -> str:
        s = s.lower()
        for pref in ["dr.", "dr ", "dr", "doctor ", "doctor"]:
            s = s.replace(pref, "")
        return " ".join(s.split())
    norm_input = normalize(doctor_name)
    doctors = db.query(Doctors).all()
    for d in doctors:
        if norm_input in normalize(d.name or ""):
            return {"doctor_id": d.doctor_id, "name": d.name}
    raise HTTPException(status_code=404, detail="Doctor not found")

@app.get("/patient_id/{patient_email}")
def get_patient_id(patient_email: str, db=Depends(get_db)):
    patient = db.query(Patients).filter(sa_func.lower(Patients.email) == patient_email.lower()).first()
    if patient:
        return {"patient_id": patient.patient_id}
    raise HTTPException(status_code=404, detail="Patient not found")

# Simple list endpoints (no response_model to avoid schema issues)
@app.get("/doctors")
def list_doctors(db=Depends(get_db)):
    rows = db.query(Doctors).all()
    return [{"doctor_id": d.doctor_id, "name": d.name} for d in rows]

@app.get("/patients")
def list_patients(db=Depends(get_db)):
    rows = db.query(Patients).all()
    return [{"patient_id": p.patient_id, "name": p.name, "email": p.email} for p in rows]

class BookRequest(BaseModel):
    patient_id: int
    start_time: str
    end_time: str
    reason: str

@app.post("/book/{doctor_id}/{date}")
def book_appointment(doctor_id: int, date: str, request: BookRequest, db=Depends(get_db)):
    availability = db.query(DoctorAvailability).filter(
        DoctorAvailability.doctor_id == doctor_id,
        DoctorAvailability.available_date == date,
        DoctorAvailability.start_time == request.start_time,
        DoctorAvailability.end_time == request.end_time,
        DoctorAvailability.is_booked == False
    ).first()

    if not availability:
        raise HTTPException(status_code=400, detail="Slot not available")

    availability.is_booked = True

    appointment = Appointments(
        doctor_id=doctor_id,
        patient_id=request.patient_id,
        appointment_date=date,
        start_time=request.start_time,
        end_time=request.end_time,
        reason=request.reason,
        status='Scheduled'
    )
    db.add(appointment)
    db.commit()

    try:
        patient = db.query(Patients).filter(Patients.patient_id == request.patient_id).first()
        doctor = db.query(Doctors).filter(Doctors.doctor_id == doctor_id).first()
        start_iso = f"{date}T{str(request.start_time)}Z"
        end_iso = f"{date}T{str(request.end_time)}Z"
        calendar_create(f"Appointment with {doctor.name if doctor else 'Doctor'}", start_iso, end_iso, attendee=patient.email if patient else None)
        if patient and patient.email:
            gmail_send(patient.email, "Appointment Confirmation", f"Your appointment is booked for {date} {request.start_time}-{request.end_time}.")
    except Exception:
        pass

    return {"message": "Appointment booked", "appointment_id": appointment.appointment_id}

@app.get("/availability_next_days/{doctor_id}/{start_date}/{days}")
def availability_next_days(doctor_id: int, start_date: str, days: int, db=Depends(get_db)):
    try:
        base = datetime.strptime(start_date, "%Y-%m-%d").date()
    except Exception:
        return []
    out = []
    for i in range(days):
        d = (base + timedelta(days=i)).isoformat()
        slots = db.query(DoctorAvailability).filter(
            DoctorAvailability.doctor_id == doctor_id,
            DoctorAvailability.available_date == d,
            DoctorAvailability.is_booked == False
        ).all()
        if slots:
            out.append({"date": d, "slots": [{
                "start_time": str(s.start_time),
                "end_time": str(s.end_time),
                "is_booked": s.is_booked
            } for s in slots]})
    return out

# Stats endpoints
@app.get("/stats/appointments_count")
def appointments_count(doctor_id: int | None = None, period: str = "today", db=Depends(get_db)):
    today = datetime.utcnow().date()
    if period == "yesterday":
        d = today - timedelta(days=1)
    elif period == "tomorrow":
        d = today + timedelta(days=1)
    else:
        d = today
    q = db.query(Appointments).filter(Appointments.appointment_date == d)
    if doctor_id:
        q = q.filter(Appointments.doctor_id == doctor_id)
    return {"date": d.isoformat(), "count": q.count()}

@app.get("/stats/appointments_count_on")
def appointments_count_on(date: str, doctor_id: int | None = None, db=Depends(get_db)):
    try:
        d = datetime.strptime(date, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date")
    q = db.query(Appointments).filter(Appointments.appointment_date == d)
    if doctor_id:
        q = q.filter(Appointments.doctor_id == doctor_id)
    return {"date": d.isoformat(), "count": q.count()}

@app.get("/stats/appointments_times")
def appointments_times(date: str, doctor_id: int | None = None, db=Depends(get_db)):
    try:
        d = datetime.strptime(date, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date")
    q = db.query(Appointments).filter(Appointments.appointment_date == d)
    if doctor_id:
        q = q.filter(Appointments.doctor_id == doctor_id)
    rows = q.order_by(Appointments.start_time.asc()).all()
    return [{
        "start_time": str(r.start_time),
        "end_time": str(r.end_time),
        "patient_id": r.patient_id,
        "doctor_id": r.doctor_id,
        "appointment_id": r.appointment_id,
    } for r in rows]

@app.get("/stats/appointments_count_range")
def appointments_count_range(start_date: str, end_date: str, doctor_id: int | None = None, db=Depends(get_db)):
    try:
        s = datetime.strptime(start_date, "%Y-%m-%d").date()
        e = datetime.strptime(end_date, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date range")
    q = db.query(Appointments).filter(Appointments.appointment_date >= s, Appointments.appointment_date <= e)
    if doctor_id:
        q = q.filter(Appointments.doctor_id == doctor_id)
    return {"start_date": s.isoformat(), "end_date": e.isoformat(), "count": q.count()}

@app.get("/stats/appointments_busiest_day")
def appointments_busiest_day(start_date: str, end_date: str, doctor_id: int | None = None, db=Depends(get_db)):
    try:
        s = datetime.strptime(start_date, "%Y-%m-%d").date()
        e = datetime.strptime(end_date, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date range")
    from sqlalchemy import func as sa_func
    q = db.query(Appointments.appointment_date, sa_func.count().label("c")).filter(Appointments.appointment_date >= s, Appointments.appointment_date <= e)
    if doctor_id:
        q = q.filter(Appointments.doctor_id == doctor_id)
    q = q.group_by(Appointments.appointment_date).order_by(sa_func.count().desc())
    row = q.first()
    if not row:
        return {"date": None, "count": 0}
    return {"date": row[0].isoformat(), "count": int(row[1])}

@app.get("/stats/reports_texts")
def reports_texts(start_date: str, end_date: str, doctor_id: int | None = None, limit: int = 200, db=Depends(get_db)):
    try:
        s = datetime.strptime(start_date, "%Y-%m-%d").date()
        e = datetime.strptime(end_date, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date range")
    q = db.query(PatientReports.symptoms, PatientReports.diagnosis).join(Appointments, PatientReports.appointment_id == Appointments.appointment_id).filter(Appointments.appointment_date >= s, Appointments.appointment_date <= e)
    if doctor_id:
        q = q.filter(Appointments.doctor_id == doctor_id)
    q = q.limit(limit)
    rows = q.all()
    return [{"symptoms": r[0] or "", "diagnosis": r[1] or ""} for r in rows]

@app.get("/stats/symptom_count")
def symptom_count(keyword: str, doctor_id: int | None = None, start_date: str | None = None, end_date: str | None = None, db=Depends(get_db)):
    q = db.query(PatientReports, Appointments).join(Appointments, PatientReports.appointment_id == Appointments.appointment_id)
    if doctor_id:
        q = q.filter(Appointments.doctor_id == doctor_id)
    if start_date:
        q = q.filter(Appointments.appointment_date >= start_date)
    if end_date:
        q = q.filter(Appointments.appointment_date <= end_date)
    q = q.filter(sa_func.lower(PatientReports.symptoms).like(f"%{keyword.lower()}%"))
    return {"keyword": keyword, "count": q.count()}

# Prompt history endpoints
@app.post("/history/log")
def history_log(role: str = Body(...), prompt: str = Body(...), response: str = Body("")):
    conn = sqlite3.connect(HISTORY_DB)
    cur = conn.cursor()
    cur.execute("INSERT INTO prompts(role, prompt, response, created_at) VALUES (?,?,?,?)", (role, prompt, response, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/history")
def history_list(limit: int = 50):
    conn = sqlite3.connect(HISTORY_DB)
    cur = conn.cursor()
    cur.execute("SELECT id, role, prompt, response, created_at FROM prompts ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "role": r[1], "prompt": r[2], "response": r[3], "created_at": r[4]} for r in rows]

# Report agent trigger
@app.post("/report")
def trigger_report(payload: dict = Body(...)):
    from report_agent import run_report
    prompt = payload.get("prompt", "")
    doctor_id = payload.get("doctor_id")
    channel = payload.get("channel", "in_app")
    result = run_report(prompt, doctor_id, channel)
    # log history
    history_log("doctor", prompt, result)
    # store notification if in_app
    if channel == "in_app":
        conn = sqlite3.connect(HISTORY_DB)
        cur = conn.cursor()
        cur.execute("INSERT INTO notifications(user, channel, message, created_at) VALUES (?,?,?,?)", (f"doctor:{doctor_id}", channel, result, datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
    return {"result": result}

# NLP parse endpoint
llm_groq = ChatGroq(model="llama3-70b-8192")

def _extract_json_py(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"```(?:json)?\s*({[\s\S]*?})\s*```", text, re.IGNORECASE)
        if m:
            cand = m.group(1)
        else:
            s = text.find('{'); e = text.rfind('}')
            cand = text[s:e+1] if s!=-1 and e!=-1 else '{}'
        cand = re.sub(r"//.*", "", cand)
        cand = re.sub(r",\s*([}\]])", r"\1", cand)
        try:
            return json.loads(cand)
        except Exception:
            return {}

def _normalize_date_py(s: str | None) -> str | None:
    if not s: return None
    sl = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", s.strip().lower())
    try:
        return datetime.strptime(sl, "%Y-%m-%d").date().isoformat()
    except: pass
    for fmt in ["%d %B %Y", "%B %d %Y", "%d %B", "%B %d", "%d-%m-%Y", "%d/%m/%Y"]:
        try:
            dt = datetime.strptime(sl.title(), fmt)
            if "%Y" not in fmt: dt = dt.replace(year=datetime.utcnow().year)
            return dt.date().isoformat()
        except: pass
    if sl=="tomorrow": return (datetime.utcnow().date()+timedelta(days=1)).isoformat()
    if sl=="today": return datetime.utcnow().date().isoformat()
    return None

def _normalize_time_py(s: str | None) -> str | None:
    if not s: return None
    t = s.strip().lower().replace(' ', '')
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?(am|pm)?$", t)
    if m:
        h = int(m.group(1)); mi=int(m.group(2) or 0); ap=m.group(3)
        if ap=='pm' and h<12: h+=12
        if ap=='am' and h==12: h=0
        return f"{h:02d}:{mi:02d}:00"
    if re.match(r"^\d{2}:\d{2}(:\d{2})?$", t):
        return t if t.count(':')==2 else f"{t}:00"
    return None

@app.post("/nlp/parse_booking")
def nlp_parse_booking(payload: dict = Body(...), db=Depends(get_db)):
    text = payload.get("text", "")
    prompt = (
        "Return ONLY JSON with: doctor_name, date (YYYY-MM-DD or natural), start_time (HH:MM or HH:MM:SS).\n"
        f"Text: {text}"
    )
    resp = llm_groq.invoke(prompt).content
    data = _extract_json_py(resp)
    name = (data.get('doctor_name') or '').strip()
    dval = _normalize_date_py(data.get('date'))
    tval = _normalize_time_py(data.get('start_time'))
    # If user didn't include a 4-digit year but model inserted a year, coerce to current year
    try:
        includes_year = bool(re.search(r"\d{4}", text))
        if dval and not includes_year:
            dt = datetime.strptime(dval, "%Y-%m-%d")
            if dt.year != datetime.utcnow().year:
                dval = dt.replace(year=datetime.utcnow().year).date().isoformat()
    except Exception:
        pass
    did = None
    if name:
        doctors = db.query(Doctors).all()
        nl = name.lower().replace('dr.', '').replace('dr ', '').strip()
        for d in doctors:
            if nl in (d.name or '').lower():
                did = d.doctor_id; break
    return {"doctor_id": did, "date": dval, "start_time": tval}

# Tool endpoints (MCP-like) for email and calendar
@app.post("/tools/send_email")
def tool_send_email(payload: dict = Body(...)):
    to = payload.get("to"); subject = payload.get("subject"); body = payload.get("body")
    try:
        gmail_send(to, subject, body)
        return {"status": "sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"send_email failed: {e}")

@app.post("/tools/create_calendar_event")
def tool_create_calendar(payload: dict = Body(...)):
    summary = payload.get("summary"); start_iso = payload.get("start_iso"); end_iso = payload.get("end_iso"); attendee = payload.get("attendee")
    try:
        calendar_create(summary, start_iso, end_iso, attendee)
        return {"status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"calendar_create failed: {e}")

@app.post("/tools/whatsapp_send")
def tool_whatsapp_send(payload: dict = Body(...)):
    to = payload.get("to")
    message = payload.get("message")
    template = payload.get("template_name")
    lang = payload.get("lang_code", "en_US")
    token = payload.get("token") or os.getenv("WHATSAPP_TOKEN")
    phone_id = payload.get("phone_id") or os.getenv("WHATSAPP_PHONE_ID")
    if not (to and (message or template) and token and phone_id):
        raise HTTPException(status_code=400, detail="Missing to/message(or template)/token/phone_id")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"https://graph.facebook.com/v22.0/{phone_id}/messages"
    if template and not message:
        payload_out = {"messaging_product":"whatsapp","to":to,"type":"template","template":{"name":template,"language":{"code":lang}}}
    else:
        payload_out = {"messaging_product":"whatsapp","to":to,"type":"text","text":{"body":message[:1000]}}
    try:
        r = requests.post(url, headers=headers, json=payload_out, timeout=15)
        return {"status": r.status_code, "response": r.text[:500]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"whatsapp_send failed: {e}")

# Helper for WhatsApp from server-side flows
def _whatsapp_send_text(to: str, message: str, token: str | None = None, phone_id: str | None = None) -> tuple[int, str]:
    token = token or os.getenv("WHATSAPP_TOKEN")
    phone_id = phone_id or os.getenv("WHATSAPP_PHONE_ID")
    if not (to and message and token and phone_id):
        return (400, "missing to/message/token/phone_id")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"https://graph.facebook.com/v22.0/{phone_id}/messages"
    payload_out = {"messaging_product":"whatsapp","to":to,"type":"text","text":{"body":message[:1000]}}
    try:
        r = requests.post(url, headers=headers, json=payload_out, timeout=15)
        if r.status_code == 200:
            return (r.status_code, r.text[:500])
        # Fallback to template if free-form blocked
        payload_tpl = {"messaging_product":"whatsapp","to":to,"type":"template","template":{"name":os.getenv("WHATSAPP_TEMPLATE","hello_world"),"language":{"code":os.getenv("WHATSAPP_LANG","en_US")}}}
        rt = requests.post(url, headers=headers, json=payload_tpl, timeout=15)
        return (rt.status_code, rt.text[:500])
    except Exception as e:
        return (500, str(e))

class RescheduleDayRequest(BaseModel):
    doctor_id: int
    from_date: str
    to_date: str
    notify: bool = True

@app.post("/appointments/reschedule_day")
def appointments_reschedule_day(req: RescheduleDayRequest, db=Depends(get_db)):
    try:
        d_from = datetime.strptime(req.from_date, "%Y-%m-%d").date()
        d_to = datetime.strptime(req.to_date, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid dates")

    # Fetch appointments to move
    appts = db.query(Appointments).filter(Appointments.doctor_id == req.doctor_id, Appointments.appointment_date == d_from).all()
    if not appts:
        return {"updated": 0, "emails": 0, "whatsapp": 0}

    emails_sent = 0
    wa_sent = 0

    # Optional patient lookups
    pats = {p.patient_id: p for p in db.query(Patients).all()}

    for a in appts:
        # Free old availability slot
        old_slot = db.query(DoctorAvailability).filter(DoctorAvailability.doctor_id == req.doctor_id, DoctorAvailability.available_date == d_from, DoctorAvailability.start_time == a.start_time, DoctorAvailability.end_time == a.end_time).first()
        if old_slot:
            old_slot.is_booked = False

        # Ensure new availability exists
        new_slot = db.query(DoctorAvailability).filter(DoctorAvailability.doctor_id == req.doctor_id, DoctorAvailability.available_date == d_to, DoctorAvailability.start_time == a.start_time, DoctorAvailability.end_time == a.end_time).first()
        if not new_slot:
            new_slot = DoctorAvailability(doctor_id=req.doctor_id, available_date=d_to, start_time=a.start_time, end_time=a.end_time, is_booked=True)
            db.add(new_slot)
        else:
            new_slot.is_booked = True

        # Move the appointment
        a.appointment_date = d_to
        a.status = 'Rescheduled'

        if req.notify:
            patient = pats.get(a.patient_id)
            if patient and patient.email:
                try:
                    gmail_send(patient.email, "Appointment shift request", f"Dear {patient.name or 'Patient'}, your appointment on {req.from_date} at {a.start_time} is requested to shift to {req.to_date} at {a.start_time}.")
                    emails_sent += 1
                except Exception:
                    pass
            if patient and patient.phone:
                status, _ = _whatsapp_send_text(patient.phone, f"Doctor requests to shift your appointment from {req.from_date} {a.start_time} to {req.to_date} {a.start_time}.")
                if status == 200:
                    wa_sent += 1

    db.commit()
    return {"updated": len(appts), "emails": emails_sent, "whatsapp": wa_sent}

# Patient agent chat endpoint (must be defined before server starts)
@app.post("/agent/patient_chat")
def patient_agent_chat(payload: dict = Body(...)):
    global patient_agent_app
    if patient_agent_app is None:
        try:
            from agent import app as _agent_app
            patient_agent_app = _agent_app
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Patient agent is not available: {e}")
    # Incoming state from client or default
    client_state = payload.get("state") or {}
    state = {
        'messages': [],
        'intent': client_state.get('intent'),
        'doctor_name': client_state.get('doctor_name'),
        'doctor_id': client_state.get('doctor_id'),
        'patient_email': client_state.get('patient_email'),
        'patient_id': client_state.get('patient_id'),
        'date': client_state.get('date'),
        'time_period': client_state.get('time_period'),
        'start_time': client_state.get('start_time'),
        'end_time': client_state.get('end_time'),
        'reason': client_state.get('reason'),
        'need_info': client_state.get('need_info', False),
    }
    text = payload.get("message", "")
    state['messages'].append(HumanMessage(content=text))
    try:
        output = patient_agent_app.invoke(state, {"recursion_limit": 50})
        # last agent message
        msg = output.get('messages', [])[-1].content if output.get('messages') else ""
        # Return updated state (excluding messages for size) and agent reply
        out_state = {k: v for k, v in output.items() if k != 'messages' and k != 'ui'}
        ui = output.get('ui')
        return {"message": msg, "state": out_state, "ui": ui}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")

# Models
class Doctors(Base):
    __tablename__ = "doctors"
    doctor_id = Column(Integer, primary_key=True)
    name = Column(String)
    specialization = Column(String)
    email = Column(String)
    phone = Column(String)
    created_at = Column(DateTime)

class Patients(Base):
    __tablename__ = "patients"
    patient_id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)
    phone = Column(String)
    date_of_birth = Column(Date)
    created_at = Column(DateTime)

class DoctorAvailability(Base):
    __tablename__ = "doctor_availability"
    availability_id = Column(Integer, primary_key=True)
    doctor_id = Column(Integer, ForeignKey("doctors.doctor_id"))
    available_date = Column(Date)
    start_time = Column(Time)
    end_time = Column(Time)
    is_booked = Column(Boolean)

class Appointments(Base):
    __tablename__ = "appointments"
    appointment_id = Column(Integer, primary_key=True)
    doctor_id = Column(Integer, ForeignKey("doctors.doctor_id"))
    patient_id = Column(Integer, ForeignKey("patients.patient_id"))
    appointment_date = Column(Date)
    start_time = Column(Time)
    end_time = Column(Time)
    reason = Column(Text)
    status = Column(String)
    created_at = Column(DateTime, server_default=func.now())

class PatientReports(Base):
    __tablename__ = "patient_reports"
    report_id = Column(Integer, primary_key=True)
    appointment_id = Column(Integer, ForeignKey("appointments.appointment_id"))
    symptoms = Column(Text)
    diagnosis = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
