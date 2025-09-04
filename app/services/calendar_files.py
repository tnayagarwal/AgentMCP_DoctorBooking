from datetime import datetime

def create_ics(summary: str, start_iso: str, end_iso: str, attendee: str | None = None) -> str:
	uid = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
	content = (
		"BEGIN:VCALENDAR\n"
		"VERSION:2.0\n"
		"BEGIN:VEVENT\n"
		f"UID:{uid}@clinic.local\n"
		f"DTSTAMP:{uid}\n"
		f"DTSTART:{start_iso.replace('-', '').replace(':', '').replace('-', '')}\n"
		f"DTEND:{end_iso.replace('-', '').replace(':', '').replace('-', '')}\n"
		f"SUMMARY:{summary}\n"
		"END:VEVENT\n"
		"END:VCALENDAR\n"
	)
	return content

