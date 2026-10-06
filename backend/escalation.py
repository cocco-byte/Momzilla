import uuid
from datetime import datetime, timezone

from backend import db
from backend.config import ESCALATION_MIN_TIER
from backend.models import EscalationRecord, RiskTier
from backend.session_store import Session

TIER_NAMES = {
    RiskTier.NONE: "none",
    RiskTier.LOW: "low",
    RiskTier.MEDIUM: "medium",
    RiskTier.HIGH: "high",
    RiskTier.IMMINENT: "imminent",
}


class Notifier:
    """Swap this out for a real transport (email/SMS/paging system/school
    SIS webhook) at deployment time. Whatever the transport, the payload
    must stay exactly this shape: no message content, ever."""

    def notify(self, record: EscalationRecord) -> None:
        raise NotImplementedError


class ConsoleNotifier(Notifier):
    """Prototype default - prints the no-detail alert instead of paging
    anyone for real."""

    def notify(self, record: EscalationRecord) -> None:
        print(
            f"[counselor alert] counselor={record.counselor_id} "
            f"student={record.student_id} tier={record.tier} "
            f"at={record.created_at.isoformat()} - "
            "student may benefit from a check-in. No further detail available."
        )


class AlertBoard:
    """Counselor dashboard backing store. Persisted to Postgres
    (backend/db.py) so an alert survives a server restart - it's
    content-free by construction (EscalationRecord has no field for
    message text), so persisting it doesn't reopen the "no human sees the
    conversation" guarantee."""

    def add(self, record: EscalationRecord) -> None:
        db.insert_escalation(
            id=record.id,
            student_id=record.student_id,
            counselor_id=record.counselor_id,
            tier=record.tier,
            created_at=record.created_at,
        )

    def for_counselor(self, counselor_id: str) -> list[EscalationRecord]:
        return [_row_to_record(row) for row in db.list_escalations_for_counselor(counselor_id)]

    def all(self) -> list[EscalationRecord]:
        return [_row_to_record(row) for row in db.list_all_escalations()]


def _row_to_record(row) -> EscalationRecord:
    # created_at comes back as a native datetime (psycopg converts
    # TIMESTAMPTZ automatically) - pydantic accepts that directly.
    return EscalationRecord(
        id=row["id"],
        student_id=row["student_id"],
        counselor_id=row["counselor_id"],
        tier=row["tier"],
        created_at=row["created_at"],
    )


board = AlertBoard()
_notifier: Notifier = ConsoleNotifier()


def maybe_escalate(session: Session, tier: RiskTier, counselor_id: str) -> EscalationRecord | None:
    """Notify at most once per tier increase within a session.

    A session that reaches MEDIUM gets one alert; if it later rises to HIGH
    or IMMINENT, that rise fires exactly one more alert each. Dropping back
    down and climbing again within the same tier does not re-notify - this
    keeps a counselor's queue meaningful instead of one row per message.
    """
    if tier < ESCALATION_MIN_TIER or tier <= session.highest_notified_tier:
        return None

    record = EscalationRecord(
        id=str(uuid.uuid4()),
        student_id=session.student_id,
        counselor_id=counselor_id,
        tier=TIER_NAMES[tier],
        created_at=datetime.now(timezone.utc),
    )
    session.highest_notified_tier = tier
    board.add(record)
    _notifier.notify(record)
    return record
