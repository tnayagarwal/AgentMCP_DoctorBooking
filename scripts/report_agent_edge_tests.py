import os
import sys
import argparse
import re
from typing import List, Tuple

# Ensure project root on path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from report_agent import run_report


DEFAULT_TESTS: List[str] = [
    # Dates and counts
    "what appointments today",
    "how many appointments on 2025-08-26",
    "how many appointments between 2025-08-24 and 2025-08-30",
    # Ordinals / variants
    "tell times on 26th",
    "tell times on 26/08",
    # Relative ranges
    "how many patients with fever last 7 days",
    "how many patients with cough last 14 days",
    # Weekday phrase
    "tell times on friday",
    # Invalid date (should not crash; should return friendly fallback)
    "tell times on 2025-13-40",
    # Busiest day (requires backend endpoint)
    "busiest day between 2025-08-24 and 2025-08-30",
    # WhatsApp only when explicitly asked
    "whatsapp me how many appointments on 2025-08-26",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run report agent edge-case tests")
    p.add_argument("--doctor-id", type=int, default=1)
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--stop-on-fail", action="store_true")
    p.add_argument("--include", nargs="*", default=None, help="Custom test prompts (replaces defaults)")
    return p.parse_args()


def is_probably_json(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    # Heuristic: raw JSON objects/arrays as entire reply, or large JSON-like structure
    if (t.startswith("{") and t.endswith("}")) or (t.startswith("[") and t.endswith("]")):
        return True
    # Many braces/quotes often indicate JSON leakage
    if len(re.findall(r'[{}\[\]"]', t)) > 20:
        return True
    return False


def run_test(prompt: str, doctor_id: int, whatsapp_default_to: str | None, verbose: bool) -> Tuple[bool, str, str]:
    raw = prompt.strip()
    channel = "in_app"
    to_number = None
    if raw.lower().startswith("whatsapp me "):
        # Only send WhatsApp when explicitly requested
        prompt = raw[len("whatsapp me "):].strip()
        channel = "whatsapp"
        to_number = whatsapp_default_to
    else:
        prompt = raw

    try:
        reply = run_report(prompt, doctor_id, channel=channel, to_number=to_number)
    except Exception as e:
        return (False, prompt, f"exception: {e}")

    if verbose:
        print(f"\nPrompt: {prompt}\nReply: {reply}")

    # Basic assertions: reply should be non-empty and not raw JSON
    if not reply or not isinstance(reply, str):
        return (False, prompt, "empty or non-string reply")
    if is_probably_json(reply):
        return (False, prompt, "reply looks like raw JSON")
    # Ensure human-friendly punctuation
    if not any(ch in reply for ch in ['.', ':']):
        return (False, prompt, "reply lacks human-friendly punctuation")
    return (True, prompt, "ok")


def main():
    args = parse_args()
    tests = args.include if args.include else DEFAULT_TESTS
    whatsapp_to = os.getenv("WHATSAPP_TO")

    print(f"Running {len(tests)} tests (doctor_id={args.doctor_id})\n")
    failures = []
    for i, t in enumerate(tests, 1):
        ok, prompt, info = run_test(t, args.doctor_id, whatsapp_to, args.verbose)
        status = "PASS" if ok else "FAIL"
        print(f"[{i:02d}] {status}: {prompt} - {info}")
        if not ok:
            failures.append((prompt, info))
            if args.stop_on_fail:
                break

    print("\nSummary:")
    print(f"  Passed: {len(tests) - len(failures)}")
    print(f"  Failed: {len(failures)}")
    if failures:
        for p, info in failures:
            print(f"   - {p}: {info}")

    # Non-zero exit on failure for CI scripting
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()


