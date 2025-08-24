import os
import sys
import argparse
import csv
from typing import List, Dict, Any
import psycopg2
from psycopg2.extras import execute_values


TABLE_ORDER = [
    "doctors",
    "patients",
    "doctor_availability",
    "appointments",
    "patient_reports",
]

PRIMARY_KEYS = {
    "doctors": "doctor_id",
    "patients": "patient_id",
    "doctor_availability": "availability_id",
    "appointments": "appointment_id",
    "patient_reports": "report_id",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import CSVs into PostgreSQL using existing credentials.")
    parser.add_argument("--host", default=os.getenv("PGHOST", "localhost"), help="PostgreSQL host")
    parser.add_argument("--port", default=os.getenv("PGPORT", "5432"), help="PostgreSQL port")
    parser.add_argument("--user", default=os.getenv("PGUSER", "postgres"), help="PostgreSQL user")
    parser.add_argument("--password", default=os.getenv("PGPASSWORD", "TaNaY"), help="PostgreSQL password")
    parser.add_argument("--dbname", default=os.getenv("PGDATABASE", "clinicdb"), help="Database name")
    parser.add_argument(
        "--dir",
        default=None,
        help="Directory that contains public/*.csv. If not provided, auto-select the latest under exports/",
    )
    parser.add_argument("--schema", default=os.getenv("PGSCHEMA", "public"), help="Target schema (default: public)")
    return parser.parse_args()


def connect_db(args: argparse.Namespace):
    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        dbname=args.dbname,
    )
    conn.autocommit = True
    return conn


def find_latest_export_dir(base: str = "exports") -> str | None:
    if not os.path.isdir(base):
        return None
    entries = [os.path.join(base, d) for d in os.listdir(base)]
    entries = [d for d in entries if os.path.isdir(d)]
    if not entries:
        return None
    # pick most recently modified
    entries.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    # expect subdir "public" under the db timestamp dir
    cand = os.path.join(entries[0], "public")
    return cand if os.path.isdir(cand) else None


def coerce_value(table: str, col: str, value: str) -> Any:
    if value == "":
        return None
    low = value.strip().lower()
    if table == "doctor_availability" and col == "is_booked":
        if low in ("true", "t", "1", "yes"):
            return True
        if low in ("false", "f", "0", "no"):
            return False
    return value


def read_csv_rows(csv_path: str, table: str) -> tuple[list[str], list[list[Any]]]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        rows: list[list[Any]] = []
        for r in reader:
            rows.append([coerce_value(table, c, r.get(c, "")) for c in cols])
        return cols, rows


def insert_rows(conn, schema: str, table: str, columns: List[str], rows: List[List[Any]]):
    if not rows:
        return 0
    pk = PRIMARY_KEYS.get(table)
    cols_sql = ", ".join([f'"{c}"' for c in columns])
    conflict_sql = f"ON CONFLICT (\"{pk}\") DO NOTHING" if pk and pk in columns else ""
    sql = f"INSERT INTO {schema}.\"{table}\" ({cols_sql}) VALUES %s {conflict_sql}".strip()
    with conn.cursor() as cur:
        execute_values(cur, sql, rows, page_size=1000)
    return len(rows)


def reset_sequence(conn, schema: str, table: str, pk: str):
    with conn.cursor() as cur:
        cur.execute("SELECT pg_get_serial_sequence(%s, %s)", (f"{schema}.{table}", pk))
        seq_row = cur.fetchone()
        if not seq_row or not seq_row[0]:
            return
        seq_name = seq_row[0]
        cur.execute(f"SELECT COALESCE(MAX({pk}), 0) FROM {schema}.\"{table}\"")
        max_id = cur.fetchone()[0] or 0
        # setval(seq, max_id), is_called true
        cur.execute("SELECT setval(%s, %s, %s)", (seq_name, max_id, True))


def main():
    args = parse_args()
    target_dir = args.dir or find_latest_export_dir()
    if not target_dir:
        print("Could not find an exports directory with CSVs. Use --dir to specify one.")
        sys.exit(1)

    print(f"Importing from: {target_dir}")
    conn = connect_db(args)
    try:
        total = 0
        for table in TABLE_ORDER:
            csv_path = os.path.join(target_dir, f"{table}.csv")
            if not os.path.isfile(csv_path):
                print(f"- Skipping {table}: {csv_path} not found")
                continue
            columns, rows = read_csv_rows(csv_path, table)
            if not rows:
                print(f"- {table}: no rows in CSV")
                continue
            inserted = insert_rows(conn, args.schema, table, columns, rows)
            print(f"- {table}: processed {inserted} rows")
            total += inserted
            # reset sequence to max id
            pk = PRIMARY_KEYS.get(table)
            if pk:
                reset_sequence(conn, args.schema, table, pk)
        print(f"Done. Processed {total} rows across tables.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()


