python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:GROQ_API_KEY = $env:GROQ_API_KEY
python scripts\seed.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
