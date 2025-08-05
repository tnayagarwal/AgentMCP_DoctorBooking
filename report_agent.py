import os
import json
import re
import requests
from datetime import datetime, timedelta, date as dt_date
from langchain_groq import ChatGroq

# LLM config (env-based, fast and deterministic)
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")
llm = ChatGroq(model=GROQ_MODEL, temperature=0.0)

BASE_URL = "http://localhost:8000"

# WhatsApp config (Meta Graph API)
WA_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WA_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
WA_TEMPLATE = os.getenv("WHATSAPP_TEMPLATE", "hello_world")
WA_LANG = os.getenv("WHATSAPP_LANG", "en_US")
WA_DEFAULT_TO = os.getenv("WHATSAPP_TO", "")

WEEKDAYS = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6
}
def _today() -> dt_date:
    override = os.getenv("REPORT_AGENT_TEST_TODAY")
    if override:
        try:
            return datetime.strptime(override, "%Y-%m-%d").date()
        except Exception:
            pass
    return dt_date.today()



def _strip_ordinal(s: str) -> str:
    return re.sub(r"(\d+)(st|nd|rd|th)", r"\1", s, flags=re.IGNORECASE)


def _parse_date_phrase(s: str) -> str | None:
    if not s:
        return None
    s = _strip_ordinal(s.strip().lower())
    today = _today()
    if s in ("today",):
        return today.isoformat()
    if s in ("yesterday",):
        return (today - timedelta(days=1)).isoformat()
    if s in ("tomorrow",):
        return (today + timedelta(days=1)).isoformat()
    if s in WEEKDAYS:
        target = WEEKDAYS[s]
        delta = (today.weekday() - target) % 7
        if delta == 0:
            delta = 7
        return (today - timedelta(days=delta)).isoformat()
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%B %d %Y", "%d %B", "%B %d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(s.title() if "%B" in fmt else s, fmt)
            if "%Y" not in fmt:
                dt = dt.replace(year=today.year)
            return dt.date().isoformat()
        except Exception:
            continue
    return None


def _interpret_query(text: str) -> dict:
    t = (text or "").strip().lower()
    # detect symptom keywords (extendable)
    symptoms = ["fever", "cough", "flu", "cold", "fatigue", "headache"]
    is_symptom = any(k in t for k in symptoms)
    keyword = None
    for k in symptoms:
        if k in t:
            keyword = k
            break
    # list times intents (include bare 'times' for follow-ups like 'times?')
    if any(p in t for p in ["show times", "tell times", "list times", "time slots", "appointment times"]) or re.search(r"\btimes\b", t):
        # detect date phrase
        m_date = re.search(r"(on|for)\s+([\w\s\-/]+)$", t)
        d = _parse_date_phrase(m_date.group(2)) if m_date else None
        d = d or _today().isoformat()
        return {"type": "list_times", "date": d}

    m = re.search(r"last\s+(\d+)\s+days", t)
    if m:
        n = int(m.group(1))
        end = _today()
        start = end - timedelta(days=n-1)
        return {"type": "count_symptom" if is_symptom else "count_appointments", "keyword": keyword, "start_date": start.isoformat(), "end_date": end.isoformat()}
    for phrase in ("yesterday", "today", "tomorrow") + tuple(WEEKDAYS.keys()):
        if phrase in t:
            d = _parse_date_phrase(phrase)
            return {"type": "count_symptom" if is_symptom else "count_appointments", "keyword": keyword, "date": d}
    m2 = re.search(r"on\s+([\w\s\-/]+)", t)
    if m2:
        d = _parse_date_phrase(m2.group(1))
        if d:
            return {"type": "count_symptom" if is_symptom else "count_appointments", "keyword": keyword, "date": d}
    return {"type": "count_symptom" if is_symptom else "count_appointments", "keyword": keyword, "date": dt_date.today().isoformat()}


def _count_appointments_for_day(doctor_id: int | None, day: str) -> int:
    # Use new count-on-date endpoint when available, fallback to limited periods
    try:
        r = requests.get(f"{BASE_URL}/stats/appointments_count_on", params={"doctor_id": doctor_id, "date": day}, timeout=10)
        if r.status_code == 200:
            return r.json().get("count", 0)
    except Exception:
        pass
    today = _today()
    period_map = {
        (today - timedelta(days=1)).isoformat(): "yesterday",
        today.isoformat(): "today",
        (today + timedelta(days=1)).isoformat(): "tomorrow",
    }
    period = period_map.get(day)
    if period:
        rr = requests.get(f"{BASE_URL}/stats/appointments_count", params={"doctor_id": doctor_id, "period": period})
        return rr.json().get("count", 0)
    return 0


def call_stats_interpreted(parsed: dict, doctor_id: int | None) -> dict:
    if parsed.get("type") == "list_times":
        d = parsed.get("date") or _today().isoformat()
        r = requests.get(f"{BASE_URL}/stats/appointments_times", params={"doctor_id": doctor_id, "date": d})
        times = r.json() if r.status_code == 200 else []
        # also fetch count for consistency checks
        try:
            rc = requests.get(f"{BASE_URL}/stats/appointments_count_on", params={"doctor_id": doctor_id, "date": d}, timeout=10)
            cnt = rc.json().get("count", 0) if rc.status_code == 200 else 0
        except Exception:
            cnt = 0
        return {"type": "list_times", "date": d, "times": times, "count": cnt}
    if parsed.get("type") == "count_symptom":
        params = {"keyword": parsed.get("keyword", "fever")}
        if doctor_id:
            params["doctor_id"] = doctor_id
        if parsed.get("start_date") and parsed.get("end_date"):
            params["start_date"] = parsed["start_date"]
            params["end_date"] = parsed["end_date"]
        elif parsed.get("date"):
            params["start_date"] = parsed["date"]
            params["end_date"] = parsed["date"]
        r = requests.get(f"{BASE_URL}/stats/symptom_count", params=params)
        return {"type": "count_symptom", "keyword": params["keyword"], "count": r.json().get("count", 0), "range": {k: params.get(k) for k in ("start_date","end_date","date") if params.get(k)}}
    else:
        if parsed.get("start_date") and parsed.get("end_date"):
            start = datetime.strptime(parsed["start_date"], "%Y-%m-%d").date()
            end = datetime.strptime(parsed["end_date"], "%Y-%m-%d").date()
            total = 0
            d = start
            while d <= end:
                total += _count_appointments_for_day(doctor_id, d.isoformat())
                d += timedelta(days=1)
            return {"type": "count_appointments", "count": total, "range": {"start_date": parsed["start_date"], "end_date": parsed["end_date"]}}
        else:
            day = parsed.get("date") or _today().isoformat()
            c = _count_appointments_for_day(doctor_id, day)
            return {"type": "count_appointments", "count": c, "date": day}


def summarize(parsed: dict, stats: dict) -> str:
    if stats.get("type") == "list_times":
        times = stats.get("times", [])
        if times:
            human = ", ".join([f"{t['start_time']}–{t['end_time']}" for t in times])
            return f"Appointments on {stats.get('date')}: {human}."
        # fallback to count if available
        cnt = stats.get("count", 0)
        if cnt > 0:
            return f"{cnt} appointments on {stats.get('date')}."
        return f"No appointments on {stats.get('date')}."
    if stats.get("type") == "count_symptom":
        rng = stats.get("range", {})
        if rng.get("start_date") and rng.get("end_date"):
            return f"{stats['count']} patients with {stats['keyword']} between {rng['start_date']} and {rng['end_date']}."
        d = rng.get("date") or parsed.get("date")
        return f"{stats['count']} patients with {stats['keyword']} on {d}."
    else:
        if stats.get("range"):
            r = stats["range"]
            return f"{stats['count']} appointments between {r['start_date']} and {r['end_date']}."
        return f"{stats['count']} appointments on {stats.get('date')}."


def _wa_send_text(to_number: str, message: str) -> requests.Response:
    headers = {"Authorization": f"Bearer {WA_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message[:1000]}
    }
    return requests.post(f"https://graph.facebook.com/v22.0/{WA_PHONE_ID}/messages", headers=headers, json=payload, timeout=10)


def _wa_send_template(to_number: str, template_name: str = None, lang_code: str = None) -> requests.Response:
    headers = {"Authorization": f"Bearer {WA_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": (template_name or WA_TEMPLATE),
            "language": {"code": (lang_code or WA_LANG)}
        }
    }
    return requests.post(f"https://graph.facebook.com/v22.0/{WA_PHONE_ID}/messages", headers=headers, json=payload, timeout=10)


def notify(channel: str, message: str, to_number: str | None = None):
    if channel != "whatsapp":
        return
    if not (WA_TOKEN and WA_PHONE_ID):
        print("[WA] Missing token/phone id; skipping WhatsApp send.")
        return
    to = (to_number or WA_DEFAULT_TO)
    if not to:
        print("[WA] Missing recipient number; set WHATSAPP_TO.")
        return
    try:
        r = _wa_send_text(to, message)
        print("[WA] text status:", r.status_code, r.text[:200])
        if r.status_code == 200:
            return
        rt = _wa_send_template(to)
        print("[WA] template status:", rt.status_code, rt.text[:200])
    except Exception as e:
        print("[WA] exception:", e)


def run_report(prompt: str, doctor_id: int | None, channel: str = "in_app", to_number: str | None = None) -> str:
    parsed = _interpret_query(prompt)
    stats = call_stats_interpreted(parsed, doctor_id)
    summary = summarize(parsed, stats)
    if channel == "whatsapp":
        notify("whatsapp", summary, to_number)
    try:
        requests.post(f"{BASE_URL}/history/log", json={"role":"doctor","prompt":prompt,"response":summary})
    except Exception:
        pass
    return summary

if __name__ == "__main__":
    print(run_report("How many patients visited yesterday?", doctor_id=1, channel="in_app"))
