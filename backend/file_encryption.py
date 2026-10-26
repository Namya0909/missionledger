"""Encrypts uploaded files at rest (currently: transaction receipts — the only file
type this app persists to disk; see routers/transactions.py). Protects against
someone with raw access to the disk/a backup, without the app's own auth, reading a
file's contents — a different concern from Render's ephemeral-disk caveat (documented
in the README), which is about files not SURVIVING a restart, not about them being
readable while they're there.

Symmetric authenticated encryption (Fernet: AES-128-CBC + HMAC) — simple, fast, no
AI/token cost. Key loaded the same way auth.py already loads JWT_SECRET: an env var
first (set via Render's generateValue: true in production), else a local gitignored
file, generated once if missing.
"""

import base64
import hashlib
import os
import secrets

from cryptography.fernet import Fernet, InvalidToken

from config import PROJECT_DIR

FILES_KEY_ENV_VAR = "FILES_ENCRYPTION_KEY"
_KEY_FILE = PROJECT_DIR / ".files_key"  # local only, gitignored


def _load_or_create_raw_secret() -> str:
    """Same pattern as auth.py's _load_or_create_secret: env var first (e.g. Render's
    generateValue: true, which produces an arbitrary random string, not necessarily a
    valid Fernet key), else a local gitignored file, generated once if missing."""
    env_secret = os.getenv(FILES_KEY_ENV_VAR)
    if env_secret:
        return env_secret
    if _KEY_FILE.exists():
        return _KEY_FILE.read_text().strip()
    secret = secrets.token_hex(32)
    _KEY_FILE.write_text(secret)
    return secret


def _derive_fernet_key(raw_secret: str) -> bytes:
    """Fernet requires a specific 32-byte urlsafe-base64 key format — derive one
    deterministically from whatever raw secret material we have (hex from a local
    file, or an arbitrary string from an env var), rather than assuming the raw
    value already happens to be in that exact format."""
    digest = hashlib.sha256(raw_secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_derive_fernet_key(_load_or_create_raw_secret()))


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet.encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    try:
        return _fernet.decrypt(token)
    except InvalidToken:
        raise ValueError("File could not be decrypted — it may be corrupted or the encryption key has changed.")
