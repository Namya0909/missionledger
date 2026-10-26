"""Password hashing and JWT-based auth."""

import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

import models
from config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET_ENV_VAR, PROJECT_DIR
from database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

_SECRET_FILE = PROJECT_DIR / ".jwt_secret"  # local only, gitignored


def _load_or_create_secret() -> str:
    env_secret = os.getenv(JWT_SECRET_ENV_VAR)
    if env_secret:
        return env_secret
    if _SECRET_FILE.exists():
        return _SECRET_FILE.read_text().strip()
    secret = secrets.token_hex(32)
    _SECRET_FILE.write_text(secret)
    return secret


JWT_SECRET = _load_or_create_secret()


# A short list of some of the most common leaked passwords (per widely-published
# breach-analysis lists) — not a full deny-list service, just a cheap, zero-dependency
# check that blocks the most trivially guessable accounts at signup.
COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789", "1234567890",
    "qwerty123", "qwertyuiop", "letmein123", "welcome123", "admin1234", "iloveyou1",
    "abc123456", "monkey123", "football1", "baseball1", "dragon123", "sunshine1",
    "princess1", "trustno1", "superman1", "123123123", "changeme1", "passw0rd",
    "p@ssw0rd1",
}


def is_common_password(password: str) -> bool:
    return password.lower() in COMMON_PASSWORDS


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


# A real bcrypt hash of an unguessable password — used so that checking a
# non-existent email still pays the same bcrypt cost as a real one. Without
# this, a login with an unregistered email returns near-instantly (verify_password
# is simply never called) while a real email takes the full bcrypt round-trip,
# a timing side-channel that reveals whether an email is registered even though
# the error message itself is identical either way.
_DUMMY_HASH = pwd_context.hash(secrets.token_urlsafe(32))


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def hash_security_answer(answer: str) -> str:
    return pwd_context.hash(answer)


def verify_security_answer(answer: str, answer_hash: str) -> bool:
    return pwd_context.verify(answer, answer_hash)


PENDING_LOGIN_MINUTES = 5


def create_pending_login_token(user_id: int) -> str:
    """A short-lived, narrow-purpose JWT for the gap between a correct password and
    correct security answers — stateless (no new server-side session table), but
    distinct from a real access token via `purpose`, so decode_pending_login_token()
    below refuses to accept one as a real access token and vice versa."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=PENDING_LOGIN_MINUTES)
    payload = {"sub": str(user_id), "purpose": "security_answers", "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_pending_login_token(token: str) -> int:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("purpose") != "security_answers":
            raise ValueError("wrong token purpose")
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login expired — please start over.")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def require_membership(
    workspace_id: int, user: models.User, db: Session
) -> models.Membership:
    membership = (
        db.query(models.Membership)
        .filter_by(workspace_id=workspace_id, user_id=user.id)
        .first()
    )
    if membership is None:
        # Local import: security_log -> models only, but auth.py is imported very
        # early (by database/model-adjacent modules too in some call paths), so
        # importing lazily here avoids any chance of a circular import at startup.
        from security_log import log_security_event

        log_security_event(
            db,
            defense="Access Control",
            action="blocked",
            detail=f"{user.email} tried to access workspace {workspace_id}, which they are not a member of.",
            workspace_id=workspace_id,
            user_id=user.id,
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this workspace")
    return membership
