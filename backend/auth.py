import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend import db

# Load .env directly here rather than relying on backend.config having run
# first - this module reads os.environ at import time below, and import
# order elsewhere shouldn't be able to silently skip that (this is the same
# class of bug that bit ANTHROPIC_API_KEY before backend.config got its own
# load_dotenv() call).
load_dotenv()

# Must be set to a long random value in production (e.g. `openssl rand -hex 32`).
# The default is only safe for local dev - anyone who reads it could forge
# counselor session tokens.
JWT_SECRET = os.environ.get("MOMZILLA_JWT_SECRET", "dev-only-insecure-secret-change-me")
JWT_ALGORITHM = "HS256"
TOKEN_TTL = timedelta(hours=12)

_bearer = HTTPBearer()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_token(counselor_id: str) -> str:
    payload = {
        "sub": counselor_id,
        "exp": datetime.now(timezone.utc) + TOKEN_TTL,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_counselor(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session token")

    counselor = db.get_counselor_by_id(payload["sub"])
    if counselor is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Counselor account no longer exists")
    return counselor
