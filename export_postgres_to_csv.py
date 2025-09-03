import os
import sys
import argparse
import psycopg2
from psycopg2 import sql
from datetime import datetime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export all tables from a PostgreSQL database to CSV files.")
    parser.add_argument("--host", default=os.getenv("PGHOST", "localhost"), help="PostgreSQL host")
    parser.add_argument("--port", default=os.getenv("PGPORT", "5432"), help="PostgreSQL port")
    parser.add_argument("--user", default=os.getenv("PGUSER", "postgres"), help="PostgreSQL user")
    parser.add_argument("--password", default=os.getenv("PGPASSWORD", "TaNaY"), help="PostgreSQL password (env PGPASSWORD takes precedence)")
    parser.add_argument("--dbname", default=os.getenv("PGDATABASE", "clinicdb"), help="Database name (default: clinicdb)")
    parser.add_argument("--schema", default=os.getenv("PGSCHEMA", "public"), help="Schema to export (default: public). Use '*' for all non-system schemas.")
    parser.add_argument("--outdir", default="exports", help="Output directory for CSV files")
    return parser.parse_args()


def connect_db(args: argparse.Namespace):
    password = os.getenv("PGPASSWORD", args.password)
    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=password,
        dbname=args.dbname,
    )
    conn.autocommit = True
    return conn


def get_schemas(cur, include_all: bool, target_schema: str):
    if include_all:
        cur.execute(
            """
            SELECT nspname
            FROM pg_namespace
            WHERE nspname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY nspname
            """
        )
        return [r[0] for r in cur.fetchall()]
    return [target_schema]


def get_tables(cur, schema: str):
    cur.execute(
        sql.SQL(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
              AND table_schema = %s
            ORDER BY table_name
            """
        ),
        [schema],
    )
    return [r[0] for r in cur.fetchall()]


def export_table(cur, schema: str, table: str, out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    query = sql.SQL("COPY {}.{} TO STDOUT WITH CSV HEADER").format(
        sql.Identifier(schema), sql.Identifier(table)
    )
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        cur.copy_expert(query, f)


def main():
    args = parse_args()
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_outdir = os.path.abspath(args.outdir)
    outdir = os.path.join(base_outdir, f"{args.dbname}-{ts}")
    os.makedirs(outdir, exist_ok=True)

    try:
        conn = connect_db(args)
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        sys.exit(1)

    try:
        with conn.cursor() as cur:
            schemas = get_schemas(cur, args.schema == "*", args.schema)
            total_tables = 0
            print(f"Exporting from database '{args.dbname}' -> {outdir}")
            for schema in schemas:
                tables = get_tables(cur, schema)
                if not tables:
                    continue
                schema_dir = os.path.join(outdir, schema)
                os.makedirs(schema_dir, exist_ok=True)
                for table in tables:
                    out_path = os.path.join(schema_dir, f"{table}.csv")
                    try:
                        export_table(cur, schema, table, out_path)
                        print(f"- {schema}.{table} -> {out_path}")
                        total_tables += 1
                    except Exception as ex:
                        print(f"! Failed to export {schema}.{table}: {ex}")
            print(f"Done. Exported {total_tables} tables.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()


