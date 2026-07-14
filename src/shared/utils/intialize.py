# utils/run.py

from uuid import uuid4

def create_run_id() -> str:
    return str(uuid4())