import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import db
from backend.auth import create_token, get_current_counselor, verify_password
from backend.chat_agent import generate_reply
from backend.config import CRISIS_RESOURCE_MIN_TIER, DEBUG_LOG_TIERS
from backend.escalation import board, maybe_escalate
from backend.models import ChatTurn
from backend.risk_classifier import classify_risk
from backend.roster import get_or_register_student
from backend.session_store import store


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Momzilla student support chat (prototype)", lifespan=lifespan)

# CORS_ALLOWED_ORIGINS should be a comma-separated list of your real
# frontend origin(s) in any deployment beyond local dev - "*" is only safe
# because auth uses a bearer token, not cookies, but it's still broader
# than it needs to be once you know the real domain.
_allowed_origins = os.environ.get("MOMZILLA_CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allowed_origins == "*" else _allowed_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    student_id: str
    session_id: str | None = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    student = get_or_register_student(req.student_id)
    session = store.get_or_create(req.session_id, student.id)

    session.history.append(ChatTurn(role="user", content=req.message))

    tier = classify_risk(session.history)
    if DEBUG_LOG_TIERS:
        print(f"[debug] session={session.id} tier={tier.name}")

    reply = generate_reply(session.history, tier, session.resources_shown)
    if tier >= CRISIS_RESOURCE_MIN_TIER:
        session.resources_shown = True

    session.history.append(ChatTurn(role="assistant", content=reply))

    maybe_escalate(session, tier, student.assigned_counselor_id)

    return ChatResponse(session_id=session.id, reply=reply)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@app.post("/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    row = db.get_counselor_by_username(req.username)
    if row is None or not verify_password(req.password, row["password_hash"]):
        # Same error for "no such user" and "wrong password" - don't let a
        # login form confirm which usernames exist.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password")
    return LoginResponse(access_token=create_token(row["id"]))


class CounselorOut(BaseModel):
    id: str
    name: str
    contact_email: str


@app.get("/auth/me", response_model=CounselorOut)
def me(counselor=Depends(get_current_counselor)):
    return CounselorOut(id=counselor["id"], name=counselor["name"], contact_email=counselor["contact_email"])


class AlertOut(BaseModel):
    id: str
    student_id: str
    tier: str
    created_at: str


@app.get("/counselor/alerts", response_model=list[AlertOut])
def counselor_alerts(counselor=Depends(get_current_counselor)):
    """Requires a valid counselor session token. Identity comes from the
    token, never from a client-supplied ID - a counselor can only ever see
    their own queue. Returns tier + student identity only; conversation
    content is never stored anywhere in this system, so there is nothing
    further to leak even if this endpoint were compromised."""
    return [
        AlertOut(id=a.id, student_id=a.student_id, tier=a.tier, created_at=a.created_at.isoformat())
        for a in board.for_counselor(counselor["id"])
    ]
