"""Short, human-typeable join codes, replacing the old long URL-safe invite token.

The old design had the server guess its own public https:// address
(`request.base_url`) to build a shareable link — on Render that's proxied over plain
HTTP to the app, so the guess came out wrong (wrong scheme, sometimes wrong host) and
the link just didn't work. A short code sidesteps that class of bug entirely: nothing
is ever built from the server's idea of its own address. The admin shares the code any
way they like (text, Slack, reading it aloud); the recipient types it in after signing
up/logging in.
"""

import secrets

from sqlalchemy.orm import Session

import models

# Excludes 0/O, 1/I/L — ambiguous when read aloud or hand-typed.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6


def generate_join_code(db: Session) -> str:
    for _ in range(10):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if not db.query(models.InviteLink).filter_by(token=code).first():
            return code
    raise RuntimeError("Could not generate a unique join code after 10 attempts")
