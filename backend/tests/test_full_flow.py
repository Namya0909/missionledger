"""One full, real run through the app: log in, upload the sample bank
statement, confirm a transaction from it, ask the assistant a question, and
generate a report — the same path a real user takes, exercised end to end.

Needs a real AI key (the chat + report-writing steps genuinely call the model),
so the whole thing skips cleanly if none is configured.
"""

from pathlib import Path

from tests.conftest import auth_headers, login, my_workspace_id, requires_ai_key

pytestmark = requires_ai_key

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
SAMPLES = PROJECT_DIR / "samples"


def test_login_upload_ask_and_report(client):
    # 1. Log in as a real demo user.
    headers = auth_headers(login(client, "maya@demo.org"))
    ws_id = my_workspace_id(client, headers)

    # 2. Upload the sample bank statement.
    with open(SAMPLES / "boa_statement_sample.csv", "rb") as f:
        r = client.post(
            f"/api/workspaces/{ws_id}/intake/statement",
            headers=headers,
            files={"file": ("boa_statement_sample.csv", f, "text/csv")},
        )
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert rows, "expected the sample statement to parse into at least one row"

    # 3. Confirm one of them into a real transaction — pin it to a pot we know
    # exists in this workspace (Rent) rather than trusting the AI's per-row pot
    # guess, so this test's outcome doesn't depend on model variance.
    row = rows[0]
    confirm_payload = {
        "rows": [
            {
                "date": row["date"],
                "merchant": row["merchant"],
                "amount": row["amount"],
                "pot_name": "Rent",
                "category": row["suggested_category"] or "Uncategorized",
                "source": "uploaded_file",
            }
        ]
    }
    r = client.post(f"/api/workspaces/{ws_id}/intake/confirm-transactions", headers=headers, json=confirm_payload)
    assert r.status_code == 200
    created = r.json()
    assert len(created) == 1
    assert created[0]["merchant"] == row["merchant"]

    # 4. Ask the assistant a real question and get a grounded, non-blocked reply.
    r = client.post(
        f"/api/workspaces/{ws_id}/chat", headers=headers, json={"message": "How much is left in Rent?"}
    )
    assert r.status_code == 200
    chat_body = r.json()
    assert chat_body["blocked"] is False
    assert chat_body["reply"], "expected a real reply, not an empty one"
    assert "$" in chat_body["reply"], "expected the answer to cite an actual dollar figure"

    # 5. Generate a PDF report.
    r = client.post(f"/api/workspaces/{ws_id}/reports/generate", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF", "response should be a real PDF file"
    assert len(r.content) > 500, "a real report should be more than a near-empty stub"
