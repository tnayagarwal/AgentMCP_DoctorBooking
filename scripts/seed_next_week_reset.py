import os
import argparse
from datetime import date as dt_date, datetime, timedelta, time as dt_time
import random
import psycopg2


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Reset appointments and seed next week's availability + historical reports.")
    p.add_argument("--host", default=os.getenv("PGHOST", "localhost"))
    p.add_argument("--port", default=os.getenv("PGPORT", "5432"))
    p.add_argument("--user", default=os.getenv("PGUSER", "postgres"))
    p.add_argument("--password", default=os.getenv("PGPASSWORD", "TaNaY"))
    p.add_argument("--dbname", default=os.getenv("PGDATABASE", "clinicdb"))
    p.add_argument("--schema", default=os.getenv("PGSCHEMA", "public"))
    p.add_argument("--week_start", default="2025-08-25", help="ISO date for Monday week start (default: 2025-08-25)")
    return p.parse_args()


def connect(args: argparse.Namespace):
    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        dbname=args.dbname,
    )
    conn.autocommit = True
    return conn


def get_doctors(conn, schema: str):
    with conn.cursor() as cur:
        cur.execute(f"SELECT doctor_id, name FROM {schema}.doctors ORDER BY doctor_id")
        return cur.fetchall()


def get_random_patient_ids(conn, schema: str, limit: int = 20):
    with conn.cursor() as cur:
        cur.execute(f"SELECT patient_id FROM {schema}.patients ORDER BY random() LIMIT %s", (limit,))
        return [r[0] for r in cur.fetchall()]


def delete_future_appointments(conn, schema: str, start_date: dt_date):
    with conn.cursor() as cur:
        cur.execute(
            f"DELETE FROM {schema}.appointments WHERE appointment_date >= %s",
            (start_date,),
        )
        # free any booked availability from that date forward
        cur.execute(
            f"UPDATE {schema}.doctor_availability SET is_booked=false WHERE available_date >= %s",
            (start_date,),
        )


def ensure_availability(conn, schema: str, doctor_id: int, d: dt_date, start: dt_time, end: dt_time):
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT 1 FROM {schema}.doctor_availability
            WHERE doctor_id=%s AND available_date=%s AND start_time=%s AND end_time=%s
            """,
            (doctor_id, d, start, end),
        )
        if cur.fetchone():
            return False
        cur.execute(
            f"""
            INSERT INTO {schema}.doctor_availability(doctor_id, available_date, start_time, end_time, is_booked)
            VALUES (%s, %s, %s, %s, false)
            """,
            (doctor_id, d, start, end),
        )
        return True


def seed_week_availability(conn, schema: str, week_start: dt_date):
    docs = get_doctors(conn, schema)
    added = 0
    for i in range(7):
        d = week_start + timedelta(days=i)
        # 10:00 to 15:00 -> slots: 10:00, 10:30, 11:00, 11:30, 12:00, 12:30, 13:00, 13:30, 14:00, 14:30
        slots = [(10, 0), (10, 30), (11, 0), (11, 30), (12, 0), (12, 30), (13, 0), (13, 30), (14, 0), (14, 30)]
        for did, _ in docs:
            for h, m in slots:
                start = dt_time(h, m)
                end_dt = (datetime.combine(dt_date(2000, 1, 1), start) + timedelta(minutes=30)).time()
                if ensure_availability(conn, schema, did, d, start, end_dt):
                    added += 1
    return added


def seed_historical_reports(conn, schema: str, per_doctor: int = 5):
    docs = get_doctors(conn, schema)
    patient_ids = get_random_patient_ids(conn, schema, limit=50)
    if not patient_ids:
        return 0
    topics = [
        ("Fever and cough", "Viral infection suspected"),
        ("Back pain", "Muscle strain"),
        ("Headache", "Migraine"),
        ("Sore throat", "Pharyngitis"),
        ("Fatigue", "Anemia workup suggested"),
        ("Skin rash", "Allergic reaction"),
        ("Stomach ache", "Gastritis"),
    ]
    added = 0
    with conn.cursor() as cur:
        for did, _ in docs:
            for i in range(per_doctor):
                # place historical appointments in the past 60-90 days
                days_ago = random.randint(60, 90)
                adate = dt_date.today() - timedelta(days=days_ago)
                start = dt_time(10, 0)
                end = dt_time(10, 30)
                pid = random.choice(patient_ids)
                reason = random.choice([t[0] for t in topics])
                cur.execute(
                    f"""
                    INSERT INTO {schema}.appointments(doctor_id, patient_id, appointment_date, start_time, end_time, reason, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'Completed') RETURNING appointment_id
                    """,
                    (did, pid, adate, start, end, reason),
                )
                appt_id = cur.fetchone()[0]
                symptoms, diagnosis = random.choice(topics)
                cur.execute(
                    f"INSERT INTO {schema}.patient_reports(appointment_id, symptoms, diagnosis) VALUES (%s, %s, %s)",
                    (appt_id, symptoms, diagnosis),
                )
                added += 1
    return added


def main():
    args = parse_args()
    week_start = datetime.strptime(args.week_start, "%Y-%m-%d").date()
    conn = connect(args)
    try:
        # 1) Delete future appointments and free slots
        delete_future_appointments(conn, args.schema, week_start)
        print(f"Deleted appointments on/after {week_start}")
        # 2) Seed availability for the specified week
        added_slots = seed_week_availability(conn, args.schema, week_start)
        print(f"Seeded {added_slots} availability slots for week starting {week_start}")
        # 3) Seed historical completed appointments + patient reports
        added_reports = seed_historical_reports(conn, args.schema, per_doctor=5)
        print(f"Inserted {added_reports} historical appointments + reports")
    finally:
        conn.close()


if __name__ == "__main__":
    main()


