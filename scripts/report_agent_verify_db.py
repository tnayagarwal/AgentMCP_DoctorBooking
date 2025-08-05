import os
import sys
import re
import argparse
from typing import Tuple, List
import requests

# Ensure project root import
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from report_agent import run_report


API = os.getenv("BASE_URL", "http://localhost:8000")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify report agent outputs against DB via API")
    p.add_argument("--doctor-id", type=int, default=1)
    p.add_argument("--dates", nargs="*", default=None, help="Dates to test (YYYY-MM-DD)")
    p.add_argument("--include-today", action="store_true", help="Also test 'today' mapped by REPORT_AGENT_TEST_TODAY if set")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def _today_override() -> str | None:
    return os.getenv("REPORT_AGENT_TEST_TODAY")


def get_expected(doctor_id: int, date: str) -> Tuple[int, List[Tuple[str, str]]]:
    # count: prefer /appointments_count_on, fallback to period mapping if unavailable
    rc = requests.get(f"{API}/stats/appointments_count_on", params={"doctor_id": doctor_id, "date": date}, timeout=10)
    count = rc.json().get("count", 0) if rc.status_code == 200 else None
    if count is None:
        # Fallback if endpoint not available in running server
        try:
            today = _today_override()
            if today == date:
                rp = requests.get(f"{API}/stats/appointments_count", params={"doctor_id": doctor_id, "period": "today"}, timeout=10)
                if rp.status_code == 200:
                    count = rp.json().get("count", 0)
        except Exception:
            pass
    if count is None:
        count = 0
    # times
    rt = requests.get(f"{API}/stats/appointments_times", params={"doctor_id": doctor_id, "date": date}, timeout=10)
    times = []
    if rt.status_code == 200:
        rows = rt.json()
        for r in rows:
            times.append((str(r.get("start_time")), str(r.get("end_time"))))
    return count, times


def parse_agent_count(text: str) -> int:
    if not text:
        return -1
    m = re.search(r"(\d+)\s+appointments", text)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass
    if "No appointments" in text:
        return 0
    return -1


def parse_agent_times(text: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    if not text or text.strip().lower().startswith("no appointments"):
        return out
    # Expect: "Appointments on DATE: HH:MM–HH:MM, HH:MM–HH:MM."
    chunk = text.split(":", 1)
    if len(chunk) < 2:
        return out
    times_part = chunk[1]
    for m in re.finditer(r"(\d{2}:\d{2})[–-](\d{2}:\d{2})", times_part):
        out.append((m.group(1) + ":00", m.group(2) + ":00"))
    return out


def compare_lists(a: List[Tuple[str, str]], b: List[Tuple[str, str]]) -> bool:
    sa = sorted(a)
    sb = sorted(b)
    return sa == sb


def main():
    args = parse_args()
    dates = args.dates or []
    if args.include_today:
        today_override = os.getenv("REPORT_AGENT_TEST_TODAY")
        if today_override:
            dates.append(today_override)
    if not dates:
        print("No dates provided. Use --dates YYYY-MM-DD [...] or --include-today with REPORT_AGENT_TEST_TODAY set.")
        sys.exit(1)

    failures = []
    for d in dates:
        exp_count, exp_times = get_expected(args.doctor_id, d)
        # Count check
        r1 = run_report(f"how many appointments on {d}", args.doctor_id)
        got_count = parse_agent_count(r1)
        ok_count = (got_count == exp_count)
        if args.verbose:
            print(f"[COUNT] {d}: expected={exp_count} got={got_count} :: {r1}")
        if not ok_count:
            failures.append((d, f"count mismatch: expected {exp_count} got {got_count}"))

        # Times check
        r2 = run_report(f"tell times on {d}", args.doctor_id)
        got_times = parse_agent_times(r2)
        ok_times = compare_lists(got_times, exp_times)
        if args.verbose:
            print(f"[TIMES] {d}: expected={exp_times} got={got_times} :: {r2}")
        if not ok_times:
            failures.append((d, "times mismatch"))

    if failures:
        print("\nVERIFICATION FAILED")
        for d, msg in failures:
            print(f" - {d}: {msg}")
        sys.exit(1)
    else:
        print("\nVERIFICATION PASSED for all dates.")


if __name__ == "__main__":
    main()


