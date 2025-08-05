import os
import sys
import argparse
from datetime import datetime, timedelta, date as dt_date, time as dt_time
import psycopg2


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed extra availability slots for testing.")
    p.add_argument("--host", default=os.getenv("PGHOST", "localhost"))
    p.add_argument("--port", default=os.getenv("PGPORT", "5432"))
    p.add_argument("--user", default=os.getenv("PGUSER", "postgres"))
    p.add_argument("--password", default=os.getenv("PGPASSWORD", "TaNaY"))
    p.add_argument("--dbname", default=os.getenv("PGDATABASE", "clinicdb"))
    p.add_argument("--schema", default=os.getenv("PGSCHEMA", "public"))
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


def ensure_slot(conn, schema: str, doctor_id: int, d: dt_date, start: dt_time, end: dt_time):
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT availability_id FROM {schema}.doctor_availability
            WHERE doctor_id=%s AND available_date=%s AND start_time=%s AND end_time=%s
            """,
            (doctor_id, d, start, end),
        )
        row = cur.fetchone()
        if row:
            return False
        cur.execute(
            f"""
            INSERT INTO {schema}.doctor_availability(doctor_id, available_date, start_time, end_time, is_booked)
            VALUES (%s, %s, %s, %s, false)
            """,
            (doctor_id, d, start, end),
        )
        return True


def main():
    args = parse_args()
    conn = connect(args)
    try:
        docs = get_doctors(conn, args.schema)
        if not docs:
            print("No doctors found; seed doctors first.")
            return

        added = 0
        today = dt_date.today()
        tomorrow = today + timedelta(days=1)

        # Seed: tomorrow afternoon 15:00-15:30 for all doctors
        for did, _name in docs:
            if ensure_slot(conn, args.schema, did, tomorrow, dt_time(15, 0), dt_time(15, 30)):
                added += 1

        # Seed: specific 2024-10-25 15:00 for any doctor whose name contains 'Ahuja'
        target_date = dt_date(2024, 10, 25)
        for did, name in docs:
            if name and "ahuja" in name.lower():
                if ensure_slot(conn, args.schema, did, target_date, dt_time(15, 0), dt_time(15, 30)):
                    added += 1
                if ensure_slot(conn, args.schema, did, target_date, dt_time(15, 30), dt_time(16, 0)):
                    added += 1

        print(f"Seed complete. Added {added} slot(s).")
    finally:
        conn.close()


if __name__ == "__main__":
    main()


