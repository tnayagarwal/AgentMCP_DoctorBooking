import time
import os
import sys
from langchain_core.messages import HumanMessage

# Ensure project root is on sys.path for importing agent.py
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent import app, AgentState


def interactive():
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
        'reason': None,
        'need_info': False,
    }
    print("Patient Agent Interactive Mode. Type 'reset' to clear state, 'exit' to quit.\n")
    while True:
        try:
            user = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()  # newline
            break
        if not user:
            continue
        if user.lower() == 'exit':
            break
        if user.lower() == 'reset':
            state.update({
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
                'reason': None,
                'need_info': False,
            })
            print("State reset.\n")
            continue
        state['messages'].append(HumanMessage(content=user))
        output = app.invoke(state, {"recursion_limit": 50})
        for k, v in output.items():
            state[k] = v
        print("Agent:", output["messages"][-1].content)
        time.sleep(0.05)


if __name__ == "__main__":
    interactive()


