from datetime import datetime
from enum import IntEnum
from pydantic import BaseModel


class RiskTier(IntEnum):
    """Ordered so comparisons (tier >= RiskTier.MEDIUM) work directly."""

    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    IMMINENT = 4

    @classmethod
    def from_str(cls, value: str) -> "RiskTier":
        return {
            "none": cls.NONE,
            "low": cls.LOW,
            "medium": cls.MEDIUM,
            "high": cls.HIGH,
            "imminent": cls.IMMINENT,
        }[value]


class Student(BaseModel):
    id: str
    display_name: str
    assigned_counselor_id: str


class Counselor(BaseModel):
    id: str
    name: str
    contact_email: str


class ChatTurn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class EscalationRecord(BaseModel):
    """What actually gets persisted for an escalation.

    Deliberately content-free: no message text, no classifier rationale,
    nothing beyond the fact that a check-in may be warranted.
    """

    id: str
    student_id: str
    counselor_id: str
    tier: str
    created_at: datetime
