"""A cheap check that a file's actual bytes match its claimed Content-Type, on top of
the existing content-type/extension allowlist (routers/transactions.py,
routers/intake.py) — a client can set Content-Type to anything regardless of what the
file really is, so this closes the "rename a script to .jpg" gap. Zero-cost: just a
byte-prefix comparison, no new dependency, no AI/token use.
"""

MAGIC_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "application/pdf": (b"%PDF-",),
}


def sniff_matches_declared_type(contents: bytes, declared_content_type: str) -> bool:
    """True if `contents` starts with the real signature for `declared_content_type`,
    or if that type has no known signature to check (e.g. a CSV, which has no magic
    bytes — those uploads are already validated structurally by their own parser)."""
    signatures = MAGIC_SIGNATURES.get(declared_content_type)
    if signatures is None:
        return True
    return any(contents.startswith(sig) for sig in signatures)
