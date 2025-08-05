import os
import sys
import argparse
from typing import Optional

# Ensure project root is on sys.path for importing report_agent.py when run from scripts/
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from report_agent import run_report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Interactive REPL to test the Doctor Report Agent")
    p.add_argument("--doctor-id", type=int, default=1, help="Default doctor_id to use (default: 1)")
    p.add_argument("--whatsapp", action="store_true", help="Start with WhatsApp sending enabled")
    p.add_argument("--to", default=None, help="Default WhatsApp recipient (e.g., 919108281677)")
    p.add_argument("--token", default=None, help="WhatsApp access token (overrides env)")
    p.add_argument("--phone-id", default=None, help="WhatsApp phone number ID (overrides env)")
    p.add_argument("--groq-model", default=None, help="Override GROQ_MODEL (e.g., llama3-8b-8192)")
    return p.parse_args()


def apply_env_overrides(args: argparse.Namespace) -> None:
    if args.token:
        os.environ["WHATSAPP_TOKEN"] = args.token
    if args.phone_id:
        os.environ["WHATSAPP_PHONE_ID"] = args.phone_id
    if args.to:
        os.environ["WHATSAPP_TO"] = args.to
    if args.groq_model:
        os.environ["GROQ_MODEL"] = args.groq_model


def print_help() -> None:
    print("Commands:")
    print("  /help                 Show this help")
    print("  /exit                 Quit")
    print("  /doctor <id>          Set doctor_id")
    print("  /whatsapp on|off      Toggle WhatsApp sending")
    print("  /to <phone>           Set WhatsApp recipient (E.164)")
    print("  /env                  Show relevant env (masked)")
    print("Type any prompt to query the report agent (e.g., 'how many patients visited yesterday?').")


def mask(s: Optional[str]) -> str:
    if not s:
        return "(not set)"
    if len(s) <= 8:
        return "****"
    return s[:4] + "…" + s[-4:]


def show_env() -> None:
    print("GROQ_MODEL:", os.getenv("GROQ_MODEL", "(default)"))
    print("WHATSAPP_PHONE_ID:", os.getenv("WHATSAPP_PHONE_ID", "(not set)"))
    print("WHATSAPP_TO:", os.getenv("WHATSAPP_TO", "(not set)"))
    print("WHATSAPP_TOKEN:", mask(os.getenv("WHATSAPP_TOKEN")))


def repl():
    args = parse_args()
    apply_env_overrides(args)

    doctor_id = args.doctor_id
    use_whatsapp = bool(args.whatsapp)
    to_number = args.to or os.getenv("WHATSAPP_TO")

    print("Report Agent Interactive Mode. Type /help for commands.\n")
    print(f"doctor_id = {doctor_id}; whatsapp = {'on' if use_whatsapp else 'off'}; to = {to_number or '(unset)'}\n")

    while True:
        try:
            line = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.startswith("/exit"):
            break
        if line.startswith("/help"):
            print_help()
            continue
        if line.startswith("/doctor "):
            try:
                doctor_id = int(line.split(" ", 1)[1])
                print(f"doctor_id set to {doctor_id}")
            except Exception:
                print("Invalid: /doctor <id>")
            continue
        if line.startswith("/whatsapp "):
            val = (line.split(" ", 1)[1] or "").strip().lower()
            if val in ("on", "true", "yes"):
                use_whatsapp = True
            elif val in ("off", "false", "no"):
                use_whatsapp = False
            else:
                print("Usage: /whatsapp on|off")
                continue
            print(f"whatsapp = {'on' if use_whatsapp else 'off'}")
            continue
        if line.startswith("/to "):
            to_number = (line.split(" ", 1)[1] or "").strip()
            os.environ["WHATSAPP_TO"] = to_number
            print(f"to = {to_number}")
            continue
        if line.startswith("/env"):
            show_env()
            continue

        channel = "whatsapp" if use_whatsapp else "in_app"
        try:
            result = run_report(line, doctor_id, channel=channel, to_number=to_number)
            print("Agent:", result)
        except Exception as e:
            print("Agent error:", e)


if __name__ == "__main__":
    repl()


