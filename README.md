## Clinic Scheduling Agent – Implementation Guide (RagaAI Case Study)

This codebase implements the “AI Scheduling Agent Case Study” requirements in `Data Science Intern - RagaAI.txt`.

### Key Features
- Patient greeting, lookup (new vs returning) with synthetic CSV-like seed data
- Smart scheduling: 60 minutes for new patients, 30 minutes for returning
- Calendar integration via ICS file generation (fallback) and optional Google APIs
- Insurance collection and validation fields (carrier, member ID, group number)
- Booking confirmation via email and optional WhatsApp (mock fallback)
- Patient intake form distribution (sample PDF included) post booking
- 3-step reminders with ability to capture confirmations (webhook stub)
- Admin Excel export for appointments and statuses

### Quick Start (Windows PowerShell)
```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:GROQ_API_KEY="<your_groq_key>"
python scripts\seed.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### API Overview
- `GET /doctors` – list doctors
- `GET /patients` – list patients
- `GET /doctors/{id}/availability/{YYYY-MM-DD}` – free slots
- `POST /appointments/book` – book with 60/30 min logic
- `GET /admin/export/appointments.xlsx` – Excel export
- `POST /nlp/parse_booking` – Groq-based JSON parse of booking text

### Demo UI (Optional)
```powershell
streamlit run scripts\demo_ui.py
```

### Environment Variables
Copy `.env.example` to `.env` and set values. Never commit secrets.

### Notes
- Alembic migrations can be added if needed. For demo, tables auto-create.
- WhatsApp and Gmail use best-effort fallbacks if credentials are missing.



