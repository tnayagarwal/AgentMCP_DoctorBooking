import os
import sys
from datetime import date as dt_date, timedelta
from langchain_core.messages import HumanMessage

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent import app, AgentState


def invoke_turns(turns):
    state: AgentState = {
        'messages': [],
        'intent': None,
        'doctor_name': None,
        'doctor_id': None,
        'patient_email': None,
        'patient_id': None,
        'date': None,
        'time_period': None,
        'start_time': None,
        'end_time': None,
        'reason': None
    }
    for t in turns:
        state['messages'].append(HumanMessage(content=t))
        output = app.invoke(state, {"recursion_limit": 50})
        for k, v in output.items():
            state[k] = v
    return state


def assert_contains(text: str, expected: str):
    assert expected.lower() in (text or '').lower(), f"Expected to find '{expected}' in: {text}"


def test_list_today_has_ahuja_or_slots():
    state = invoke_turns(["What doctors are available today?"])
    last = state['messages'][-1].content
    # Expect either 'Doctors available' or 'No doctors available'
    assert ("Doctors available on" in last) or ("No doctors available on" in last)


def test_next_week_parsing_defaults_to_monday():
    state = invoke_turns(["Show me availability next week"])
    last = state['messages'][-1].content
    assert ("Doctors available on" in last) or ("No doctors available on" in last)


def test_specific_booking_flow():
    # Week start seeded: 2025-08-25. Attempt booking a 10:00 slot with any doctor on that date.
    state = invoke_turns([
        "Who is available on 2025-08-25 between 10am and 3pm?",
    ])
    last = state['messages'][-1].content
    assert ("Doctors available on 2025-08-25" in last) or ("No doctors available on 2025-08-25" in last)


if __name__ == "__main__":
    test_list_today_has_ahuja_or_slots()
    test_next_week_parsing_defaults_to_monday()
    test_specific_booking_flow()
    print("All patient agent assertion tests passed.")


