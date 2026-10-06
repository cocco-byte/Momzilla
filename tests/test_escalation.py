import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.escalation import AlertBoard, ConsoleNotifier, maybe_escalate
import backend.escalation as escalation_module
from backend.models import RiskTier
from backend.session_store import Session


def fresh_board(monkeypatch):
    board = AlertBoard()
    monkeypatch.setattr(escalation_module, "board", board)
    monkeypatch.setattr(escalation_module, "_notifier", ConsoleNotifier())
    return board


def test_low_tier_never_escalates(monkeypatch):
    board = fresh_board(monkeypatch)
    session = Session(id="s1", student_id="student-demo")
    assert maybe_escalate(session, RiskTier.LOW, "counselor-1") is None
    assert board.all() == []


def test_medium_tier_escalates_once(monkeypatch):
    board = fresh_board(monkeypatch)
    session = Session(id="s1", student_id="student-demo")
    first = maybe_escalate(session, RiskTier.MEDIUM, "counselor-1")
    assert first is not None
    assert len(board.all()) == 1

    # Same tier again this session should not re-notify.
    second = maybe_escalate(session, RiskTier.MEDIUM, "counselor-1")
    assert second is None
    assert len(board.all()) == 1


def test_escalating_further_notifies_again(monkeypatch):
    board = fresh_board(monkeypatch)
    session = Session(id="s1", student_id="student-demo")
    maybe_escalate(session, RiskTier.MEDIUM, "counselor-1")
    escalated = maybe_escalate(session, RiskTier.IMMINENT, "counselor-1")
    assert escalated is not None
    assert len(board.all()) == 2
    # all() is newest-first (dashboard order), so index 0 is the latest.
    assert board.all()[0].tier == "imminent"


def test_alerts_never_carry_message_content(monkeypatch):
    board = fresh_board(monkeypatch)
    session = Session(id="s1", student_id="student-demo")
    record = maybe_escalate(session, RiskTier.HIGH, "counselor-1")
    dumped = record.model_dump()
    assert set(dumped.keys()) == {"id", "student_id", "counselor_id", "tier", "created_at"}
