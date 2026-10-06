import threading
import uuid
from dataclasses import dataclass, field

from backend.models import ChatTurn, RiskTier


@dataclass
class Session:
    id: str
    student_id: str
    history: list[ChatTurn] = field(default_factory=list)
    highest_notified_tier: RiskTier = RiskTier.NONE
    resources_shown: bool = False


class SessionStore:
    """Process-memory-only conversation storage.

    Nothing here is written to disk, a database, or a log. That is the
    entire mechanism behind "no human can see the conversation": there is
    no persistence layer and no admin view of message content for anyone -
    including a counselor - to read. Restarting the process drops all
    conversation history by design.
    """

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def get_or_create(self, session_id: str | None, student_id: str) -> Session:
        with self._lock:
            if session_id and session_id in self._sessions:
                return self._sessions[session_id]
            new_id = session_id or str(uuid.uuid4())
            session = Session(id=new_id, student_id=student_id)
            self._sessions[new_id] = session
            return session


store = SessionStore()
