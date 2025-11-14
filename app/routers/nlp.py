from fastapi import APIRouter, Body, HTTPException
from app.config import settings
from langchain_groq import ChatGroq
import json, re
from datetime import datetime, timedelta, date as dt_date

router = APIRouter(prefix="/nlp", tags=["nlp"])

_llm = None

def _get_llm():
	global _llm
	if _llm is None:
		_llm = ChatGroq(model=settings.groq_model)
	return _llm

def extract_json(text: str) -> dict:
	try:
		return json.loads(text)
	except Exception:
		m = re.search(r"```(?:json)?\s*({[\s\S]*?})\s*```", text, re.IGNORECASE)
		if m:
			cand = m.group(1)
		else:
			s = text.find('{'); e = text.rfind('}')
			cand = text[s:e+1] if s!=-1 and e!=-1 else '{}'
		cand = re.sub(r",\s*([}\]])", r"\1", cand)
		try:
			return json.loads(cand)
		except Exception:
			return {}


def normalize_date(s: str | None) -> str | None:
	if not s: return None
	sl = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", s.strip().lower())
	try:
		return datetime.strptime(sl, "%Y-%m-%d").date().isoformat()
	except Exception:
		for fmt in ["%d %B %Y", "%B %d %Y", "%d %B", "%B %d", "%d-%m-%Y", "%d/%m/%Y"]:
			try:
				dt = datetime.strptime(sl.title(), fmt)
				if "%Y" not in fmt: dt = dt.replace(year=dt_date.today().year)
				return dt.date().isoformat()
			except Exception:
				continue
	if sl=="tomorrow": return (dt_date.today()+timedelta(days=1)).isoformat()
	if sl=="today": return dt_date.today().isoformat()
	return None


def normalize_time(s: str | None) -> str | None:
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

@router.post("/parse_booking")
def nlp_parse_booking(payload: dict = Body(...)):
	text = payload.get("text", "")
	prompt = (
		"Return ONLY JSON with: intent, doctor_name, date (YYYY-MM-DD or natural), start_time (HH:MM or HH:MM:SS), "
		"patient_email, reason, visit_type (new|returning), location."
		f" Text: {text}"
	)
	resp = _get_llm().invoke(prompt).content
	data = extract_json(resp)
	data['date'] = normalize_date(data.get('date'))
	data['start_time'] = normalize_time(data.get('start_time'))
	return data
