import os
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import requests
from app.config import settings

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def _gmail_service():
	try:
		from googleapiclient.discovery import build
		from google.oauth2.credentials import Credentials
		creds = Credentials.from_authorized_user_file(settings.google_token_file or 'token.json', SCOPES)
		return build('gmail', 'v1', credentials=creds)
	except Exception:
		return None


def send_email(to_email: str, subject: str, body: str) -> bool:
	service = _gmail_service()
	if not service:
		return False
	msg = MIMEText(body)
	msg['to'] = to_email
	msg['subject'] = subject
	raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
	try:
		service.users().messages().send(userId='me', body={'raw': raw}).execute()
		return True
	except Exception:
		return False


def send_email_with_attachment(to_email: str, subject: str, body: str, filepath: str) -> bool:
	service = _gmail_service()
	if not service:
		return False
	msg = MIMEMultipart()
	msg['to'] = to_email
	msg['subject'] = subject
	msg.attach(MIMEText(body))
	try:
		with open(filepath, 'rb') as f:
			part = MIMEBase('application', 'octet-stream')
			part.set_payload(f.read())
			encoders.encode_base64(part)
			part.add_header('Content-Disposition', f'attachment; filename="{filepath.split('/')[-1]}"')
			msg.attach(part)
		raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
		service.users().messages().send(userId='me', body={'raw': raw}).execute()
		return True
	except Exception:
		return False

def whatsapp_send_text(message: str, to: str | None = None) -> tuple[int, str]:
	token = settings.whatsapp_token
	phone_id = settings.whatsapp_phone_id
	to_num = to or settings.whatsapp_to
	if not (token and phone_id and to_num):
		return (400, 'missing-config')
	headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
	payload = {"messaging_product":"whatsapp","to":to_num,"type":"text","text":{"body":message[:1000]}}
	try:
		r = requests.post(f"https://graph.facebook.com/v22.0/{phone_id}/messages", headers=headers, json=payload, timeout=10)
		if r.status_code == 200:
			return (200, r.text[:300])
		# fallback to template
		payload_tpl = {"messaging_product":"whatsapp","to":to_num,"type":"template","template":{"name":settings.whatsapp_template,"language":{"code":settings.whatsapp_lang}}}
		rt = requests.post(f"https://graph.facebook.com/v22.0/{phone_id}/messages", headers=headers, json=payload_tpl, timeout=10)
		return (rt.status_code, rt.text[:300])
	except Exception as e:
		return (500, str(e))
