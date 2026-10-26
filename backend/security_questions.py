"""The security-question pool used at signup (pick 1) and login (answer that same
one, along with the password) — also used for account recovery (routers/auth.py's
/recover/* endpoints) when the password itself is forgotten. Server-authoritative —
the frontend fetches this via GET /auth/security-questions rather than hardcoding its
own copy, so there's exactly one place that defines the pool.

Deliberately a STRICT dropdown of 10 example answers per question, not free text: no
typos/case mismatches to fight at login, at the cost of a bounded answer space (only
10 options — 1-in-10 for someone who already knows which question an account uses).
That's intentionally not a secret on its own — the existing login rate limit and
10-strikes lockout (routers/auth.py) are what actually make guessing impractical, and
with only 1 question now (down from 3) they're doing noticeably more of the real
work than before. Same "documented as such, not oversold" spirit as the app's PII
redaction.
"""

SECURITY_QUESTIONS: dict[str, dict] = {
    "color": {
        "question": "What is your favorite color?",
        "options": ["Red", "Orange", "Yellow", "Green", "Blue", "Purple", "Pink", "Black", "White", "Teal"],
    },
    "pet": {
        "question": "What is your favorite type of pet?",
        "options": ["Dog", "Cat", "Bird", "Fish", "Rabbit", "Hamster", "Turtle", "Horse", "Snake", "Hedgehog"],
    },
    "food": {
        "question": "What is your favorite food?",
        "options": ["Pizza", "Sushi", "Tacos", "Pasta", "Burgers", "Salad", "Steak", "Curry", "Sandwiches", "Ice cream"],
    },
    "sport": {
        "question": "What is your favorite sport?",
        "options": ["Soccer", "Basketball", "Football", "Baseball", "Tennis", "Swimming", "Running", "Volleyball", "Golf", "Hockey"],
    },
    "music": {
        "question": "What music genre do you like most?",
        "options": ["Pop", "Rock", "Hip-Hop", "Jazz", "Classical", "Country", "R&B", "Electronic", "Folk", "Reggae"],
    },
    "ice_cream": {
        "question": "What is your favorite ice cream flavor?",
        "options": ["Vanilla", "Chocolate", "Strawberry", "Mint Chip", "Cookie Dough", "Rocky Road", "Pistachio", "Coffee", "Caramel", "Cookies and Cream"],
    },
    "holiday": {
        "question": "What is your favorite holiday?",
        "options": ["New Year's", "Valentine's Day", "Easter", "Independence Day", "Halloween", "Thanksgiving", "Christmas", "Hanukkah", "Diwali", "Lunar New Year"],
    },
    "vacation": {
        "question": "What's your preferred vacation type?",
        "options": ["Beach", "Mountains", "City", "Camping", "Cruise", "Road Trip", "Theme Park", "Countryside", "Island", "Staycation"],
    },
    "subject": {
        "question": "What was your favorite school subject?",
        "options": ["Math", "Science", "English", "History", "Art", "Music", "Phys Ed", "Computer Science", "Foreign Language", "Geography"],
    },
    "weather": {
        "question": "What is your favorite kind of weather?",
        "options": ["Sunny", "Rainy", "Snowy", "Windy", "Cloudy", "Foggy", "Stormy", "Breezy", "Humid", "Cool and crisp"],
    },
}


def question_pool() -> list[dict]:
    """[{key, question, options}, ...] in a stable order, for the frontend to render."""
    return [{"key": key, "question": q["question"], "options": q["options"]} for key, q in SECURITY_QUESTIONS.items()]


def is_valid_answer(question_key: str, answer: str) -> bool:
    question = SECURITY_QUESTIONS.get(question_key)
    return question is not None and answer in question["options"]
