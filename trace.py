"""Append-only JSONL audit log. Tokens are redacted before anything is written (I2)."""

import json
import os
import re
from datetime import datetime, timezone

SECRET = re.compile(r"(ya29\.[A-Za-z0-9_\-]+|Bearer\s+\S+|sk-or-[A-Za-z0-9]+)")


def redact(value):
    if isinstance(value, str):
        return SECRET.sub("[REDACTED]", value)
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


def trace(session: str, node: str, **fields) -> None:
    os.makedirs("traces", exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session": session,
        "node": node,
        **redact(fields),
    }
    with open(f"traces/{session}.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")
