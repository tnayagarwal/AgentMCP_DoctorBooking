import os
import argparse
import psycopg2
from datetime import datetime, time as dt_time


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed booked appointment times for a doctor on a date")
    p.add_argument("--doctor-id", type=int, required=True)
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--slots", nargs="+", required=True, help="Slots as HH:MM-HH:MM (e.g., 10:00-10:30 10:30-11:00)")
    p.add_argument("--patient-id", type=int, default=1)
    p.add_argument("--reason", default="Seeded booking")
    # DB creds (defaults match app.py local setup)
    p.add_argument("--dsn", default=os.getenv("DATABASE_URL", "postgresql://postgres:TaNaY@localhost:5432/clinicdb"))
    return p.parse_args()


def to_time(s: str) -> str:
    s = s.strip()
    if len(s) == 5 and s.count(":") == 1:
        return f"{s}:00"
    return s


def main():
    args = parse_args()
    date_str = args.date
    # Validate date
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        raise SystemExit("Invalid --date, expected YYYY-MM-DD")

    conn = psycopg2.connect(args.dsn)
    conn.autocommit = True
    cur = conn.cursor()
    try:
        for slot in args.slots:
            try:
                st, et = slot.split("-")
            except ValueError:
                print(f"Skipping invalid slot: {slot}")
                continue
            st_sql = to_time(st)
            et_sql = to_time(et)

            # Ensure availability exists
            cur.execute(
                """
                SELECT availability_id FROM doctor_availability
                WHERE doctor_id=%s AND available_date=%s AND start_time=%s AND end_time=%s
                """,
                (args.doctor_id, date_str, st_sql, et_sql),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    """
                    INSERT INTO doctor_availability(doctor_id, available_date, start_time, end_time, is_booked)
                    VALUES (%s, %s, %s, %s, TRUE)
                    """,
                    (args.doctor_id, date_str, st_sql, et_sql),
                )
            else:
                cur.execute(
                    "UPDATE doctor_availability SET is_booked=TRUE WHERE availability_id=%s",
                    (row[0],),
                )

            # Insert appointment if not exists
            cur.execute(
                """
                SELECT appointment_id FROM appointments
                WHERE doctor_id=%s AND patient_id=%s AND appointment_date=%s AND start_time=%s AND end_time=%s
                """,
                (args.doctor_id, args.patient_id, date_str, st_sql, et_sql),
            )
            ap = cur.fetchone()
            if ap is None:
                cur.execute(
                    """
                    INSERT INTO appointments(doctor_id, patient_id, appointment_date, start_time, end_time, reason, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'Scheduled')
                    RETURNING appointment_id
                    """,
                    (args.doctor_id, args.patient_id, date_str, st_sql, et_sql, args.reason),
                )
                new_id = cur.fetchone()[0]
                print(f"Seeded appointment {new_id} {date_str} {st_sql}-{et_sql}")
            else:
                print(f"Appointment exists for {date_str} {st_sql}-{et_sql}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()


