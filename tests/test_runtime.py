import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import BaseModel

from sandbox_producthunt.cli import snapshot_day
from sandbox_producthunt.locking import RunAlreadyActive, exclusive_run_lock
from sandbox_producthunt.runtime import DSHError, parse_events


class Output(BaseModel):
    ok: bool


def event_stream(*, reason="completed", answer='{"ok":true}', extra=(), session="s1"):
    events = [
        {"type": "session", "sessionId": "s1"},
        *extra,
        {"type": "final", "sessionId": session, "reason": {"kind": reason}, "text": answer},
    ]
    return ("\n".join(json.dumps(x) for x in events) + "\n").encode()


def test_valid_events():
    assert parse_events(event_stream(), 0, Output).ok


@pytest.mark.parametrize("raw,code", [
    (event_stream(), 1),
    (event_stream(reason="error"), 0),
    (event_stream(answer="not JSON"), 0),
    (event_stream(answer='{"wrong":true}'), 0),
    (event_stream(extra=({"type":"tool_call"},)), 0),
    (event_stream(session="different"), 0),
    (b"invalid\n", 0),
    (b'{"type":"session"}\n', 0),
])
def test_failed_events(raw, code):
    with pytest.raises(DSHError):
        parse_events(raw, code, Output)


def test_lock(tmp_path: Path):
    lock = tmp_path / "run.lock"
    with exclusive_run_lock(lock):
        with pytest.raises(RunAlreadyActive):
            with exclusive_run_lock(lock):
                pass
    with exclusive_run_lock(lock):
        pass


def test_date():
    assert snapshot_day("2026-11-25") == date(2026, 11, 25)
    with pytest.raises(ValueError):
        snapshot_day("20261125")
