import csv, random
from datetime import datetime, timedelta

random.seed(42)

def generate_patients_csv(path: str, n: int = 50):
	with open(path, 'w', newline='', encoding='utf-8') as f:
		w = csv.writer(f)
		w.writerow(['name','email','phone'])
		for i in range(1, n+1):
			w.writerow([f'Patient {i}', f'patient{i}@example.com', f'+9100000{i:04d}'])


def generate_schedule_csv(path: str):
	with open(path, 'w', newline='', encoding='utf-8') as f:
		w = csv.writer(f)
		w.writerow(['doctor_name','date','start_time','end_time'])
		start = datetime.utcnow().date()
		for doc in ('Dr. Ahuja','Dr. Mehra'):
			for day in range(0,5):
				dt = start + timedelta(days=day)
				for hh in (9,10,11,14,15,16):
					w.writerow([doc, dt.isoformat(), f"{hh:02d}:00:00", f"{hh:02d}:30:00"]) 

if __name__ == '__main__':
	generate_patients_csv('patients.csv')
	generate_schedule_csv('schedule.csv')
	print('Generated patients.csv and schedule.csv')
