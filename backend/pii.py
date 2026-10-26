"""Redacts personal information before it ever reaches an AI call — plain regex
matching, deterministic, no AI involved in deciding what counts as PII. Applied
to chat messages and every piece of file-extracted text before it's used in a
prompt, so a leaked SSN or card number in a message or an uploaded file never
makes it to the model (or gets echoed back in a reply).

Name pseudonymization ("Donor-1", "Donor-2") is explicitly best-effort: real
name detection needs an NLP/NER model this app doesn't have. The heuristic here
(title-case word pairs that don't look like a merchant/org name) will miss
plenty of real names and occasionally flag a non-name — it's a deterrent, not
a guarantee, and is documented as such rather than oversold.
"""

import re

SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
EIN_RE = re.compile(r"\b\d{2}-\d{7}\b")
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
# A bare 9-digit number is the standard US bank routing-number length; an
# "account number"-labeled run is matched separately (ACCOUNT_RE) since account
# numbers have no fixed length/format and are only identifiable by context.
ROUTING_RE = re.compile(r"\b\d{9}\b")
ACCOUNT_RE = re.compile(r"\baccount\s*(?:number|#|no\.?)?\s*[:#]?\s*(\d{6,17})\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?1[-.\s]?)?\(?\b\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
ADDRESS_RE = re.compile(
    # Non-greedy middle group — a greedy one spans across separate addresses in
    # the same message, swallowing everything between the first street number
    # and the LAST street-suffix word in the whole text.
    r"\b\d{1,6}\s+[A-Za-z0-9.\s]{2,30}?\b(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Ct|Court|Way)\b\.?",
    re.IGNORECASE,
)
# Capitalized word pairs ("Jordan Lee") — used only for pseudonymize_names, not redact_pii.
NAME_PAIR_RE = re.compile(r"\b[A-Z][a-z]+\s[A-Z][a-z]+\b")
# A title/role word directly before a name pair ("Donor Jordan Lee") — matched
# first so "Donor" itself is never mistaken for someone's first name.
TITLE_WORDS = ("Donor", "Mr", "Mrs", "Ms", "Dr", "Treasurer", "Board Member")
TITLED_NAME_RE = re.compile(
    rf"\b(?:{'|'.join(TITLE_WORDS)})\.?\s+([A-Z][a-z]+\s[A-Z][a-z]+)\b"
)
# Merchant/org-ish words that disqualify a capitalized pair from looking like a person's name.
NON_NAME_WORDS = {
    "inc", "llc", "co", "corp", "company", "fund", "grant", "foundation", "bank",
    "market", "energy", "realty", "wireless", "services", "supplies", "rental",
    "transit", "authority", "wholesale", "payout", "fees", "savings", "account",
}


def _luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def redact_pii(text: str) -> tuple[str, dict[str, int]]:
    """Returns (redacted_text, counts_by_category). Order matters: more specific
    patterns (SSN, EIN) run before the broader digit-sequence ones (card,
    routing) so a 9-digit routing number inside a longer card-like run doesn't
    get double-matched."""
    counts: dict[str, int] = {}

    def _replace(pattern: re.Pattern, label: str, text: str, keep_last4: bool = False) -> str:
        def repl(m: re.Match) -> str:
            counts[label] = counts.get(label, 0) + 1
            if keep_last4:
                digits = re.sub(r"\D", "", m.group())
                return f"[{label}-{digits[-4:]}]"
            return f"[{label}]"
        return pattern.sub(repl, text)

    text = _replace(SSN_RE, "SSN", text)
    text = _replace(EIN_RE, "EIN", text)
    text = _replace(EMAIL_RE, "EMAIL", text)
    text = _replace(ADDRESS_RE, "ADDRESS", text)

    # Card numbers: only redact digit runs that pass a Luhn check, to avoid
    # false-positiving on things like long order/invoice numbers.
    def card_repl(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn_valid(digits):
            counts["CARD"] = counts.get("CARD", 0) + 1
            return f"[CARD-{digits[-4:]}]"
        return m.group()

    text = CARD_RE.sub(card_repl, text)

    # Context-labeled account numbers before the generic phone/routing patterns,
    # since otherwise a bare digit run gets mislabeled as whichever pattern
    # happens to match its length first.
    def account_repl(m: re.Match) -> str:
        counts["ACCOUNT"] = counts.get("ACCOUNT", 0) + 1
        return f"[ACCOUNT-{m.group(1)[-4:]}]"

    text = ACCOUNT_RE.sub(account_repl, text)
    text = _replace(PHONE_RE, "PHONE", text)
    text = _replace(ROUTING_RE, "ROUTING", text)

    return text, counts


def pseudonymize_names(text: str) -> str:
    """Best-effort: replaces capitalized word pairs that don't look like a
    merchant/org name with consistent Donor-1, Donor-2, ... labels. Same name
    gets the same number everywhere in the text, via one shared mapping."""
    mapping: dict[str, str] = {}

    def label_for(name: str) -> str:
        if name not in mapping:
            mapping[name] = f"Donor-{len(mapping) + 1}"
        return mapping[name]

    # Pass 1: a title/role word directly before a name ("Donor Jordan Lee") —
    # matched first, and the title word is dropped, so it's never mistaken for
    # part of the name itself.
    def titled_repl(m: re.Match) -> str:
        return label_for(m.group(1))

    text = TITLED_NAME_RE.sub(titled_repl, text)

    # Pass 2: any remaining plain name pairs with no title word in front.
    def pair_repl(m: re.Match) -> str:
        candidate = m.group()
        if any(word in candidate.lower() for word in NON_NAME_WORDS):
            return candidate
        return label_for(candidate)

    return NAME_PAIR_RE.sub(pair_repl, text)
