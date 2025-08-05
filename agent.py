import os
import json
import requests
from datetime import datetime, timedelta, date as dt_date
import re
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.graph.message import MessagesState
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
from email.mime.text import MIMEText
import base64
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnablePassthrough
from typing import TypedDict, Annotated
from langchain_core.messages import AnyMessage
from datetime import date
import urllib.parse

# Groq setup
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is not set. Please set the environment variable before running.")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")
llm = ChatGroq(model=GROQ_MODEL, temperature=0.0)

# Google API setup (optional at runtime)
SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/gmail.send']
try:
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    calendar_service = build('calendar', 'v3', credentials=creds)
    gmail_service = build('gmail', 'v1', credentials=creds)
except Exception:
    creds = None
    calendar_service = None
    gmail_service = None

# FastAPI endpoints
BASE_URL = "http://localhost:8000"

class AvailabilityInput(BaseModel):
    doctor_name: str = Field(description="Name of the doctor")
    date: str = Field(description="Date in YYYY-MM-DD format")
    time_period: str = Field(description="Time period, e.g., afternoon")

class BookInput(BaseModel):
    doctor_name: str = Field(description="Name of the doctor")
    date: str = Field(description="Date in YYYY-MM-DD format")
    start_time: str = Field(description="Start time in HH:MM")
    patient_name: str = Field(description="Patient's name")
    patient_email: str = Field(description="Patient's email")
    reason: str = Field(description="Reason for appointment")

# Tools
def check_availability(doctor_id: int, date: str):
    response = requests.get(f"{BASE_URL}/availability/{doctor_id}/{date}")
    if response.status_code == 200:
        return response.json()
    return []

def book_appointment(doctor_id: int, date: str, start_time: str, end_time: str, patient_id: int, reason: str):
    payload = {
        "patient_id": patient_id,
        "start_time": start_time,
        "end_time": end_time,
        "reason": reason
    }
    response = requests.post(f"{BASE_URL}/book/{doctor_id}/{date}", json=payload)
    return response.json()

def create_calendar_event(summary, start_time, end_time, attendee_email):
    if not calendar_service:
        return None
    event = {
        'summary': summary,
        'start': {'dateTime': start_time, 'timeZone': 'UTC'},
        'end': {'dateTime': end_time, 'timeZone': 'UTC'},
        'attendees': [{'email': attendee_email}]
    }
    try:
        return calendar_service.events().insert(calendarId='primary', body=event).execute()
    except Exception:
        return None

def send_email(to, subject, body):
    if not gmail_service:
        return None
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    try:
        gmail_service.users().messages().send(userId="me", body={'raw': raw}).execute()
    except Exception:
        return None

# Robust parsing helpers

def _extract_json(text: str) -> dict:
    try:
        # Try plain JSON first
        return json.loads(text)
    except Exception:
        # Extract code block
        m = re.search(r"```(?:json)?\s*({[\s\S]*?})\s*```", text, re.IGNORECASE)
        if m:
            candidate = m.group(1)
        else:
            # Fallback: first balanced braces
            start = text.find('{')
            end = text.rfind('}')
            candidate = text[start:end+1] if start != -1 and end != -1 else '{}'
        # Strip // comments
        candidate = re.sub(r"//.*", "", candidate)
        # Remove trailing commas
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            return json.loads(candidate)
        except Exception:
            return {}

def _normalize_date(s: str | None) -> str | None:
    if not s:
        return None
    sl = s.strip().lower()
    today = dt_date.today()
    if sl in ["today", "todays"]:
        return today.strftime("%Y-%m-%d")
    if "tomorrow" in sl:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    # remove ordinal suffixes
    sl = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", sl)
    # ordinal-only day like "26"
    if re.fullmatch(r"\d{1,2}", sl):
        try:
            day = int(sl)
            cand = dt_date(today.year, today.month, min(day, 28) if day > 28 else day)
            if cand < today:
                nm = today.month + 1
                ny = today.year + (1 if nm > 12 else 0)
                nm = 1 if nm > 12 else nm
                cand = dt_date(ny, nm, min(day, 28) if day > 28 else day)
            return cand.strftime("%Y-%m-%d")
        except Exception:
            pass
    for fmt in ["%Y-%m-%d", "%d %B %Y", "%B %d %Y", "%d %B", "%B %d", "%d-%m-%Y", "%d/%m/%Y"]:
        try:
            dt = datetime.strptime(sl.title() if "%B" in fmt else sl, fmt)
            if "%Y" not in fmt:
                dt = dt.replace(year=today.year)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            continue
    return None

def _normalize_time(s: str | None) -> str | None:
    if not s:
        return None
    t = s.strip().lower().replace(" ", "")
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?(am|pm)?$", t)
    if m:
        h = int(m.group(1))
        mi = int(m.group(2) or 0)
        ap = m.group(3)
        if ap == 'pm' and h < 12:
            h += 12
        if ap == 'am' and h == 12:
            h = 0
        return f"{h:02d}:{mi:02d}"
    # Already HH:MM
    if re.match(r"^\d{2}:\d{2}$", t):
        return t
    return None

# LLM parsing using robust JSON extraction

def llm_parse(query: str) -> dict:
    prompt = (
        "Return ONLY a JSON object with keys: intent, doctor_name, date, time_period, start_time, "
        "patient_email, reason. Interpret natural language dates/times."
        " intent is one of [list_doctors, check_availability, book_appointment]."
        " Do not add comments or extra text."
        f"\nQuery: {query}"
    )
    resp = llm.invoke(prompt).content
    data = _extract_json(resp)
    # Normalize
    data['date'] = _normalize_date(data.get('date'))
    data['start_time'] = _normalize_time(data.get('start_time'))
    # Ensure doctor_name has 'Dr.' prefix if a name present
    if data.get('doctor_name') and not data['doctor_name'].lower().startswith('dr'):
        data['doctor_name'] = f"Dr. {data['doctor_name'].strip()}"
    # Normalize intent
    if data.get('intent'):
        data['intent'] = str(data['intent']).strip().lower()
    return data

reschedule_prompt = PromptTemplate(
    input_variables=["availability"],
    template="Suggest alternative slots based on availability: {availability}"
)

# Update State to include more fields and use checkpoint for persistence
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], "add_messages"]
    intent: str
    doctor_name: str
    doctor_id: int
    patient_email: str
    patient_id: int
    date: str
    time_period: str
    start_time: str
    end_time: str
    reason: str
    need_info: bool

# Remove memory line
# memory = {"configurable": {"thread_id": "test_thread"}}

# Lookup functions
def get_doctor_id(name):
    encoded = urllib.parse.quote(name)
    response = requests.get(f"{BASE_URL}/doctor_id/{encoded}")
    if response.status_code == 200:
        return response.json()["doctor_id"]
    return None

def get_patient_id(email):
    encoded = urllib.parse.quote(email)
    response = requests.get(f"{BASE_URL}/patient_id/{encoded}")
    if response.status_code == 200:
        return response.json()["patient_id"]
    return None

# Helper: fetch doctors/patients and LLM-rank the best match

def fetch_doctors():
    r = requests.get(f"{BASE_URL}/doctors")
    return r.json() if r.status_code == 200 else []

def fetch_patients():
    r = requests.get(f"{BASE_URL}/patients")
    return r.json() if r.status_code == 200 else []

def llm_choose_id(name_or_email: str, candidates: list, kind: str) -> int | None:
    prompt = (
        f"From this {kind} list, return ONLY a JSON with id field for the best match to: {name_or_email}.\n"
        f"Candidates: {json.dumps(candidates)}"
    )
    resp = llm.invoke(prompt).content
    data = _extract_json(resp)
    return data.get('id') or data.get(f'{kind[:-1]}_id')

# Update parse_input to use llm_parse

def parse_input(state: AgentState) -> dict:
    query = state['messages'][-1].content
    parsed = llm_parse(query)
    print("Parsed:", parsed)

    changes: dict = {}
    if parsed.get("doctor_name"):
        changes['doctor_name'] = parsed["doctor_name"]
        did = get_doctor_id(parsed["doctor_name"])
        if did:
            changes['doctor_id'] = did
    if parsed.get("intent"):
        changes['intent'] = parsed["intent"]
    if parsed.get("date"):
        changes['date'] = parsed["date"]
    if parsed.get("time_period"):
        changes['time_period'] = parsed["time_period"]
    if parsed.get("start_time"):
        changes['start_time'] = parsed["start_time"]
    if parsed.get("patient_email"):
        changes['patient_email'] = parsed["patient_email"]
        pid = get_patient_id(parsed["patient_email"])
        if pid:
            changes['patient_id'] = pid
    if parsed.get("reason"):
        changes['reason'] = parsed["reason"]

    # Light natural-language date guards for consistency (still LLM-first)
    try:
        ql = query.lower()
        today = dt_date.today()
        # If LLM returned a past date but user said 'tomorrow' or 'today', correct it
        if 'date' in changes and changes['date']:
            dval = datetime.strptime(changes['date'], "%Y-%m-%d").date()
            if dval < today:
                if 'tomorrow' in ql:
                    changes['date'] = (today + timedelta(days=1)).strftime("%Y-%m-%d")
                elif 'today' in ql:
                    changes['date'] = today.strftime("%Y-%m-%d")
        # Handle 'next week' → next Monday, override if model produced an irrelevant past date
        if 'next week' in ql:
            dow = today.weekday()  # Monday=0
            days_until_next_monday = (7 - dow) % 7 or 7
            next_monday = today + timedelta(days=days_until_next_monday)
            if not changes.get('date'):
                changes['date'] = next_monday.strftime("%Y-%m-%d")
            else:
                try:
                    dval = datetime.strptime(changes['date'], "%Y-%m-%d").date()
                    if dval < next_monday:
                        changes['date'] = next_monday.strftime("%Y-%m-%d")
                except Exception:
                    changes['date'] = next_monday.strftime("%Y-%m-%d")
    except Exception:
        pass

    # Intent fallback heuristics (LLM-first, minimal nudges)
    effective_for_intent = {**state, **changes}
    allowed_intents = {"list_doctors", "check_availability", "book_appointment"}
    intent_val = (effective_for_intent.get('intent') or '').strip().lower()
    if intent_val not in allowed_intents:
        ql = query.lower()
        if 'book' in ql or 'confirm' in ql:
            changes['intent'] = 'book_appointment'
        elif effective_for_intent.get('doctor_name') or effective_for_intent.get('doctor_id'):
            changes['intent'] = 'check_availability'
        else:
            changes['intent'] = 'list_doctors'

    # Compute end_time if start_time provided
    start_time_val = changes.get('start_time') or state.get('start_time')
    end_time_val = changes.get('end_time') or state.get('end_time')
    if start_time_val and not end_time_val:
        try:
            start_dt = datetime.strptime(start_time_val, "%H:%M")
            end_dt = start_dt + timedelta(minutes=30)
            changes['end_time'] = end_dt.strftime("%H:%M")
        except Exception:
            pass

    # If parsed doctor_name yields no ID, try list-based selection
    if parsed.get("doctor_name") and not changes.get('doctor_id'):
        # Try list-based selection
        doc_list = fetch_doctors()
        sel = llm_choose_id(parsed["doctor_name"], doc_list, "doctors")
        if sel:
            changes['doctor_id'] = sel
            changes['doctor_name'] = next((d['name'] for d in doc_list if d['doctor_id'] == sel), parsed['doctor_name'])

    # If parsed patient_email yields no ID, try list-based selection
    if parsed.get("patient_email") and not changes.get('patient_id'):
        pat_list = fetch_patients()
        sel = llm_choose_id(parsed["patient_email"], pat_list, "patients")
        if sel:
            changes['patient_id'] = sel
            changes['patient_email'] = next((p['email'] for p in pat_list if p['patient_id'] == sel), parsed.get('patient_email'))

    effective = {**state, **changes}
    # If the intent is to list doctors' availability, we don't require a specific doctor_id
    if (effective.get('intent') or '') == 'list_doctors':
        # Default the date to today if missing
        if not effective.get('date'):
            changes['date'] = dt_date.today().strftime("%Y-%m-%d")
        return {**changes, "messages": [AIMessage(content="Parsed input. Listing doctors' availability...")]} 

    # Otherwise, for checking/booking we need doctor and date
    missing = []
    if not effective.get('doctor_id'):
        missing.append('doctor name')
    if not effective.get('date'):
        missing.append('date')
    if missing:
        changes['need_info'] = True
        return {**changes, "messages": [AIMessage(content=f"Please provide: {', '.join(missing)}.")], "need_info": True}

    return {**changes, "messages": [AIMessage(content="Parsed input. Checking availability...")]} 

# Period filtering function

def _match_period(slot_start: str, period: str) -> bool:
    try:
        hour = int(slot_start.split(':')[0])
        p = (period or '').lower()
        if p == 'morning':
            return hour < 12
        if p == 'afternoon':
            return 12 <= hour < 17
        if p == 'evening':
            return hour >= 17
    except Exception:
        pass
    return True

# Helper to fetch next 7 days availability for a doctor
def get_next_7_days(doctor_id: int, start_date: str):
    try:
        response = requests.get(f"{BASE_URL}/availability_next_days/{doctor_id}/{start_date}/7")
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return []

# Add book_node
def book_node(state: AgentState):
    missing = []
    if not state.get('doctor_id'):
        missing.append('doctor name')
    if not state.get('date'):
        missing.append('date')
    if not state.get('start_time'):
        missing.append('start_time')
    if missing:
        ask = " and ".join(missing)
        return {"messages": [AIMessage(content=f"Missing information for booking: {', '.join(missing)}. Please provide {ask}.")], "need_info": True}
    start_time = f"{state['start_time']}:00" if len(state['start_time'].split(':')) == 2 else state['start_time']
    end_time = f"{state['end_time']}:00" if state.get('end_time') and len(state['end_time'].split(':')) == 2 else state.get('end_time')
    if not end_time:
        try:
            st = datetime.strptime(state['start_time'], "%H:%M") + timedelta(minutes=30)
            end_time = st.strftime("%H:%M:00")
        except Exception:
            end_time = "00:30:00"

    booking = book_appointment(state['doctor_id'], state['date'], start_time, end_time, state.get('patient_id') or 1, state.get('reason') or "General Checkup")

    if "appointment_id" in booking:
        start_dt = datetime.strptime(f"{state['date']} {start_time}", "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(f"{state['date']} {end_time}", "%Y-%m-%d %H:%M:%S")
        notif_info = []
        try:
            if calendar_service:
                create_calendar_event(f"Appointment with {state.get('doctor_name','Doctor')}", start_dt.isoformat(), end_dt.isoformat(), state.get('patient_email') or "")
                notif_info.append("calendar event")
        except Exception:
            pass
        try:
            if gmail_service and state.get('patient_email'):
                send_email(state['patient_email'], "Appointment Confirmation", f"Your appointment is booked for {state['date']} at {state['start_time']}.")
                notif_info.append("email")
        except Exception:
            pass
        suffix = f" Notifications sent: {', '.join(notif_info)}." if notif_info else " Notifications not sent (email/calendar not configured)."
        return {"messages": [AIMessage(content=f"Appointment booked successfully.{suffix}")]} 
    return {"messages": [AIMessage(content="Failed to book appointment.")]} 

# Update check_availability_node to return chosen slot in changes

def check_availability_node(state: AgentState):
    if not state['doctor_id'] or not state['date']:
        return {"messages": [AIMessage(content="Please provide doctor name and date.")]}
    
    availability = check_availability(state['doctor_id'], state['date'])

    # Filter
    if state.get('start_time'):
        filtered = [slot for slot in availability if slot.get("start_time") == f"{state['start_time']}:00" and not slot["is_booked"]]
    elif state.get('time_period'):
        filtered = [s for s in availability if _match_period(s.get('start_time', '00:00:00'), state['time_period']) and not s['is_booked']]
    else:
        filtered = [slot for slot in availability if not slot["is_booked"]]

    if not filtered:
        alternatives = get_next_7_days(state['doctor_id'], state['date'])
        if not alternatives:
            return {"messages": [AIMessage(content="No availability found in the next week. Please try another doctor or date.")],
                    "ui": {"type": "alternatives", "alternatives": []}} 
        return {"messages": [AIMessage(content=f"No slots on {state['date']}. Here are options on the next days.")],
                "ui": {"type": "alternatives", "alternatives": alternatives}} 

    # If specific time not provided, show options
    if not state.get('start_time'):
        msg = f"Available on {state['date']}: " + ", ".join([s['start_time'][:-3] if s['start_time'].endswith(':00') else s['start_time'] for s in filtered])
        return {"messages": [AIMessage(content=msg)],
                "ui": {"type": "results", "date": state['date'], "results": [{"doctor_id": state['doctor_id'], "doctor_name": state.get('doctor_name',''), "slots": filtered}]}} 

    # If we got a specific time and it exists, persist slot and ask to confirm booking
    slot = filtered[0]
    return {"start_time": slot['start_time'][:-3] if slot['start_time'].endswith(":00") else slot['start_time'],
            "end_time": slot['end_time'][:-3] if slot['end_time'].endswith(":00") else slot['end_time'],
            "messages": [AIMessage(content=f"Slot at {state['start_time']} is available. Say 'book' to confirm.")],
            "ui": {"type": "selected", "date": state['date'], "doctor_id": state['doctor_id'], "doctor_name": state.get('doctor_name',''), "slot": {"start_time": slot['start_time'], "end_time": slot['end_time']}}} 

# Update decide_to_book to handle more cases
def decide_to_book(state: AgentState):
    last_message = state['messages'][-1].content.lower()
    # Only proceed to book if a concrete time has been selected or provided
    if ("book" in last_message or "yes" in last_message) and state.get('start_time'):
        return "book"
    else:
        return END

# New: node to list availability across doctors for a date/period
def list_availability_node(state: AgentState):
    date = state.get('date') or dt_date.today().strftime("%Y-%m-%d")
    period = state.get('time_period')
    doctors = fetch_doctors()
    results = []
    for d in doctors:
        try:
            slots = check_availability(d['doctor_id'], date)
            if period:
                slots = [s for s in slots if not s['is_booked'] and _match_period(str(s.get('start_time','00:00:00')), period)]
            else:
                slots = [s for s in slots if not s['is_booked']]
            if slots:
                results.append({
                    "doctor_id": d['doctor_id'],
                    "doctor_name": d.get('name', ''),
                    "specialization": d.get('specialization', ''),
                    "slots": [{
                        "start_time": s.get('start_time'),
                        "end_time": s.get('end_time')
                    } for s in slots]
                })
        except Exception:
            continue
    if not results:
        # As a fallback, show the soonest next date with availability for each doctor
        alt = []
        for d in doctors:
            nxt = get_next_7_days(d['doctor_id'], date)
            if nxt:
                # take the first date that has slots matching period if provided
                chosen = None
                for day in nxt:
                    day_slots = day.get('slots', [])
                    if period:
                        day_slots = [s for s in day_slots if _match_period(str(s.get('start_time','00:00:00')), period)]
                    if day_slots:
                        chosen = {"date": day.get('date'), "slot": day_slots[0]}
                        break
                if chosen:
                    alt.append({
                        "doctor_id": d['doctor_id'],
                        "doctor_name": d.get('name', ''),
                        "next_available": chosen
                    })
        if not alt:
            return {"messages": [AIMessage(content=f"No doctors have availability on {date} or the next 7 days.")],
                    "ui": {"type": "alternatives", "alternatives": []}} 
        msg = f"No doctors available on {date}. I found options on the next days."
        return {"messages": [AIMessage(content=msg)], "ui": {"type": "alternatives", "alternatives": alt}} 
    doctors_str = ", ".join([f"{r['doctor_name']} ({len(r['slots'])} slots)" for r in results])
    msg = f"Doctors available on {date}: {doctors_str}. Tap a time below to pick."
    return {"messages": [AIMessage(content=msg)], "ui": {"type": "results", "date": date, "results": results}} 

# Decide next action after parsing
def decide_next_action(state: AgentState):
    intent = (state.get('intent') or '').lower()
    # If user asked to check availability but provided no doctor, treat as a listing request
    if intent == 'list_doctors' or (intent == 'check_availability' and not (state.get('doctor_id') or state.get('doctor_name'))):
        return 'list'
    if state.get('need_info'):
        return 'clarify'
    return 'check'

# Update graph
workflow = StateGraph(AgentState)
workflow.add_node("parse", parse_input)
workflow.add_node("list", list_availability_node)
workflow.add_node("check", check_availability_node)
workflow.add_node("book", book_node)
workflow.add_node("clarify", lambda state: {"messages": [AIMessage(content="Please provide the missing details so I can proceed.")]})

workflow.set_entry_point("parse")
workflow.add_conditional_edges("parse", decide_next_action, {"list": "list", "check": "check", "clarify": "clarify"})
workflow.add_conditional_edges("check", decide_to_book, {"book": "book", END: END})
workflow.add_edge("clarify", "parse")
workflow.add_edge("book", END)

app = workflow.compile()

# For run_conversation, use a local state dict
def run_conversation():
    local_state = {
        'messages': [],
        'doctor_name': None,
        'doctor_id': None,
        'patient_email': None,
        'patient_id': None,
        'date': None,
        'time_period': None,
        'start_time': None,
        'end_time': None,
        'reason': None
    }
    while True:
        query = input("User: ")
        if query.lower() == "exit":
            break
        local_state['messages'].append(HumanMessage(content=query))
        inputs = local_state
        output = app.invoke(inputs, {"recursion_limit": 50})
        local_state.update(output)
        print("Agent:", output["messages"][-1].content)

# Run example
GLOBAL_STATE = {
    'messages': [],
    'doctor_name': None,
    'doctor_id': None,
    'patient_email': None,
    'patient_id': None,
    'date': None,
    'time_period': None,
    'start_time': None,
    'end_time': None,
    'reason': None
}

def run_agent(query):
    GLOBAL_STATE['messages'].append(HumanMessage(content=query))
    output = app.invoke(GLOBAL_STATE)
    # merge updates back
    for k, v in output.items():
        GLOBAL_STATE[k] = v
    print("Agent:", output['messages'][-1].content)

if __name__ == "__main__":
    # Test scenarios
    print("Testing multi-turn conversation")
    #run_conversation()
    
    # Scenario 1: Available slota
    run_agent("I want to check Dr. Ahuja’s availability for 2024-10-25 afternoon.")
    run_agent("Please book the 3 PM slot.")  # Simulating second prompt, but need state
    
    # Note: For proper multi-turn testing, use the conversation loop
