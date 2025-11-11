import streamlit as st
import requests

API = st.secrets.get("API", "http://localhost:8000")

st.title("Clinic Scheduling Demo")

col1, col2 = st.columns(2)
with col1:
	text = st.text_input("Say something (e.g., 'Check Dr. Ahuja tomorrow afternoon'):")
with col2:
	if st.button("Parse"):
		resp = requests.post(f"{API}/nlp/parse_booking", json={"text": text})
		st.json(resp.json())

st.header("Quick Endpoints")
if st.button("List Doctors"):
	st.json(requests.get(f"{API}/doctors").json())

