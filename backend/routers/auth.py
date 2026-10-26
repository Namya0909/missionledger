from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from auth import (
    _DUMMY_HASH,
    create_access_token,
    create_pending_login_token,
    decode_pending_login_token,
    get_current_user,
    hash_password,
    hash_security_answer,
    is_common_password,
    verify_password,
    verify_security_answer,
)
from database import get_db
from ratelimit import is_rate_limited, record_attempt
from security_log import log_security_event
from security_questions import SECURITY_QUESTIONS, is_valid_answer, question_pool

router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_RATE_LIMIT = 5
LOGIN_RATE_WINDOW_SECONDS = 15 * 60
LOCKOUT_THRESHOLD = 10
LOCKOUT_DURATION = timedelta(hours=1)

# A real bcrypt hash, used the same way auth._DUMMY_HASH is — so verifying a security
# answer against a question_key the user never actually set still pays the same
# bcrypt cost as a real check (defense in depth; in practice step 2 only runs for a
# user_id decoded from an already-issued pending ticket, so this mostly guards
# against a malformed/forged question_key rather than email enumeration).
_DUMMY_ANSWER_HASH = hash_security_answer("placeholder-never-matches")


@router.get("/security-questions", response_model=list[schemas.SecurityQuestionOut])
def get_security_questions():
    return question_pool()


@router.post("/signup", response_model=schemas.Token)
def signup(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter_by(email=payload.email.lower()).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "An account with that email already exists")
    if is_common_password(payload.password):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "That password is too common and easy to guess — please choose a different one.",
        )

    question_keys = [a.question_key for a in payload.security_answers]
    if len(set(question_keys)) != 3:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Please choose 3 different security questions")
    for a in payload.security_answers:
        if not is_valid_answer(a.question_key, a.answer):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Please pick one of the listed answers for each security question")

    user = models.User(
        name=payload.name,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    for a in payload.security_answers:
        db.add(models.SecurityAnswer(user_id=user.id, question_key=a.question_key, answer_hash=hash_security_answer(a.answer)))
    db.commit()

    token = create_access_token(user.id)
    return schemas.Token(access_token=token, user=schemas.UserOut.model_validate(user))


@router.post("/login", response_model=schemas.LoginStep1Response)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.lower()

    # A short rolling throttle on WRONG attempts only (independent of the
    # persistent 10-strikes lockout below) — a legitimate user logging in
    # successfully several times in a row (multiple tabs/devices, an expired
    # token) never counts against this; only repeated failures do. This same
    # bucket is also charged by wrong security answers in verify_security below,
    # since those are just as much a "wrong login attempt" as a wrong password.
    if is_rate_limited(f"login:{email}", limit=LOGIN_RATE_LIMIT, window_seconds=LOGIN_RATE_WINDOW_SECONDS):
        log_security_event(
            db, defense="Rate Limiting", action="throttled",
            detail=f"Login throttled for {email}: more than {LOGIN_RATE_LIMIT} wrong attempts in 15 minutes.",
            user_id=None,
        )
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many login attempts. Please wait a few minutes and try again.",
        )

    user = db.query(models.User).filter_by(email=email).first()

    if user and user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This account is temporarily locked after too many failed attempts. Try again later.",
        )

    # Always run a real bcrypt verify, even when the user doesn't exist, so the
    # response time doesn't itself reveal whether an email is registered.
    password_ok = verify_password(payload.password, user.password_hash if user else _DUMMY_HASH)

    if user is None or not password_ok:
        record_attempt(f"login:{email}", window_seconds=LOGIN_RATE_WINDOW_SECONDS)
        if user is not None:
            user.failed_login_count += 1
            if user.failed_login_count >= LOCKOUT_THRESHOLD:
                user.locked_until = datetime.utcnow() + LOCKOUT_DURATION
                log_security_event(
                    db, defense="Login Lockout", action="locked",
                    detail=f"Account locked after {user.failed_login_count} failed login attempts.",
                    user_id=user.id,
                )
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")

    # Password's correct — don't issue the real token yet. Show that account's own
    # 3 security questions and require those too before completing the login.
    answers = db.query(models.SecurityAnswer).filter_by(user_id=user.id).all()
    questions = [
        schemas.SecurityQuestionOut(
            key=a.question_key,
            question=SECURITY_QUESTIONS[a.question_key]["question"],
            options=SECURITY_QUESTIONS[a.question_key]["options"],
        )
        for a in answers
    ]
    ticket = create_pending_login_token(user.id)
    return schemas.LoginStep1Response(login_ticket=ticket, questions=questions)


@router.post("/login/verify-security", response_model=schemas.Token)
def verify_security(payload: schemas.SecurityAnswerVerify, db: Session = Depends(get_db)):
    user_id = decode_pending_login_token(payload.login_ticket)
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login expired — please start over.")
    email = user.email

    # Same throttle bucket login() uses — wrong security answers must cost the same
    # budget as wrong passwords, not a free unlimited-guessing side channel.
    if is_rate_limited(f"login:{email}", limit=LOGIN_RATE_LIMIT, window_seconds=LOGIN_RATE_WINDOW_SECONDS):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many login attempts. Please wait a few minutes and try again.",
        )
    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This account is temporarily locked after too many failed attempts. Try again later.",
        )

    stored = {a.question_key: a.answer_hash for a in db.query(models.SecurityAnswer).filter_by(user_id=user.id).all()}
    all_correct = len(payload.answers) == 3 and all(
        verify_security_answer(a.answer, stored.get(a.question_key, _DUMMY_ANSWER_HASH)) for a in payload.answers
    )

    if not all_correct:
        record_attempt(f"login:{email}", window_seconds=LOGIN_RATE_WINDOW_SECONDS)
        user.failed_login_count += 1
        if user.failed_login_count >= LOCKOUT_THRESHOLD:
            user.locked_until = datetime.utcnow() + LOCKOUT_DURATION
            log_security_event(
                db, defense="Login Lockout", action="locked",
                detail=f"Account locked after {user.failed_login_count} failed login attempts.",
                user_id=user.id,
            )
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect answers. Please try again.")

    user.failed_login_count = 0
    user.locked_until = None
    db.commit()

    token = create_access_token(user.id)
    return schemas.Token(access_token=token, user=schemas.UserOut.model_validate(user))


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user
