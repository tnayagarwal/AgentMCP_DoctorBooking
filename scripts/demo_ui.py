import streamlit as st
import requests
from datetime import date

API = st.secrets.get("API", "http://localhost:8000")

st.title("Clinic Scheduling Demo")

st.subheader("NLP Parse")
text = st.text_input("Ask (e.g., 'Check Dr. Ahuja tomorrow afternoon'):")
if st.button("Parse with Groq"):
	resp = requests.post(f"{API}/nlp/parse_booking", json={"text": text})
	st.json(resp.json())

st.subheader("Browse & Book")
doctors = requests.get(f"{API}/doctors").json()
if not isinstance(doctors, list):
	st.warning("API not reachable yet.")
else:
	doc_map = {f"{d['name']} (#{d['doctor_id']})": d['doctor_id'] for d in doctors}
	choice = st.selectbox("Doctor", list(doc_map.keys()))
	doc_id = doc_map.get(choice)
	d = st.date_input("Date", value=date.today())
	if st.button("Fetch availability"):
		av = requests.get(f"{API}/doctors/{doc_id}/availability/{d.isoformat()}").json()
		st.session_state['slots'] = av
		st.json(av)
	slots = st.session_state.get('slots', [])
	if slots:
		opt = st.selectbox("Pick a slot", [f"{s['start_time']} - {s['end_time']}" for s in slots])
		patient_email = st.text_input("Patient email", "patient1@example.com")
		reason = st.text_input("Reason", "General Checkup")
		if st.button("Book now"):
			start_time = opt.split(' - ')[0]
			pid = requests.get(f"{API}/patients").json()[0]['patient_id']
			payload = {"doctor_id": doc_id, "patient_id": pid, "date": d.isoformat(), "start_time": start_time, "reason": reason}
			res = requests.post(f"{API}/appointments/book", json=payload)
			st.json(res.json())

