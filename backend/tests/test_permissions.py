"""Each role can do what it should and can't do what it shouldn't, and nobody can
ever see another workspace. All of this is pure permission-checking against the
already-seeded demo data — no AI calls, so it always runs.
"""

import pytest

from tests.conftest import auth_headers, login, my_workspace_id

# One demo user per role, with the exact capabilities ROLE_CAPABILITIES in
# permissions.py says that role should have. "create_transaction" is checked via
# POST /transactions; "manage_pots" via POST /pots; "manage_members" via
# POST /members; "view_security_log" via GET /security-log.
ROLE_CASES = [
    # email, create_transaction?, manage_pots?, manage_members?, view_security_log?
    ("maya@demo.org", True, True, True, True),  # group admin
    ("josh@demo.org", True, False, False, False),  # group member
    ("treasurer@demo.org", False, True, True, True),  # nonprofit treasurer (no create_transaction!)
    ("volunteer@demo.org", True, False, False, False),  # nonprofit volunteer
    ("board@demo.org", False, False, False, False),  # nonprofit board member (view-only)
    ("owner@demo.org", False, True, True, True),  # business owner (no create_transaction!)
    ("staff@demo.org", True, False, False, False),  # business staff
    ("bookkeeper@demo.org", False, False, False, False),  # business bookkeeper (view-only)
]


@pytest.mark.parametrize("email,can_create_txn,can_manage_pots,can_manage_members,can_view_log", ROLE_CASES)
def test_role_capabilities(client, email, can_create_txn, can_manage_pots, can_manage_members, can_view_log):
    headers = auth_headers(login(client, email))
    ws_id = my_workspace_id(client, headers)

    # create_transaction — probe with a pot that exists in every seeded workspace
    # type; a 403 means "your role can't", anything else means the attempt was at
    # least authorized (a 404/422 for a bad pot name would be a real test bug, so
    # assert directly against 403 either way).
    pots = client.get(f"/api/workspaces/{ws_id}/pots", headers=headers).json()
    assert pots, f"expected {email}'s workspace to have at least one pot"
    pot_id = pots[0]["id"]
    r = client.post(
        f"/api/workspaces/{ws_id}/transactions",
        headers=headers,
        json={"pot_id": pot_id, "date": "2026-01-15", "merchant": "Permission Test", "amount": 1.23},
    )
    if can_create_txn:
        assert r.status_code == 200, f"{email} should be able to add an expense: {r.status_code} {r.text}"
    else:
        assert r.status_code == 403, f"{email} should NOT be able to add an expense: got {r.status_code}"

    # manage_pots
    r = client.post(
        f"/api/workspaces/{ws_id}/pots",
        headers=headers,
        json={"name": f"Permission Test Pot ({email})", "type": "free_use"},
    )
    if can_manage_pots:
        assert r.status_code == 200, f"{email} should be able to create a pot: {r.status_code} {r.text}"
    else:
        assert r.status_code == 403, f"{email} should NOT be able to create a pot: got {r.status_code}"

    # manage_members
    r = client.post(
        f"/api/workspaces/{ws_id}/members",
        headers=headers,
        json={"email": f"nobody-{email}", "role": "member"},
    )
    if can_manage_members:
        # A bad/unparseable invitee is still fine here — we only care whether the
        # role check itself (403) fires before validation does.
        assert r.status_code != 403, f"{email} should NOT be blocked by role for managing members: {r.status_code} {r.text}"
    else:
        assert r.status_code == 403, f"{email} should NOT be able to manage members: got {r.status_code}"

    # view_security_log
    r = client.get(f"/api/workspaces/{ws_id}/security-log", headers=headers)
    if can_view_log:
        assert r.status_code == 200, f"{email} should be able to view the security log: {r.status_code} {r.text}"
    else:
        assert r.status_code == 403, f"{email} should NOT be able to view the security log: got {r.status_code}"


def test_nobody_sees_another_workspace(client):
    maya = auth_headers(login(client, "maya@demo.org"))
    owner = auth_headers(login(client, "owner@demo.org"))

    maya_ws = my_workspace_id(client, maya)
    owner_ws = my_workspace_id(client, owner)
    assert maya_ws != owner_ws

    # Maya's own workspace list never contains Corner Coffee Co.'s id, and vice versa.
    maya_list = {w["id"] for w in client.get("/api/workspaces", headers=maya).json()}
    owner_list = {w["id"] for w in client.get("/api/workspaces", headers=owner).json()}
    assert owner_ws not in maya_list
    assert maya_ws not in owner_list

    # Maya can't fetch Corner Coffee Co.'s workspace, pots, transactions, members,
    # or security log directly by id/url, even though she's a legitimate,
    # logged-in user — just not a member of THIS workspace.
    for path in [
        f"/api/workspaces/{owner_ws}",
        f"/api/workspaces/{owner_ws}/pots",
        f"/api/workspaces/{owner_ws}/transactions",
        f"/api/workspaces/{owner_ws}/members",
        f"/api/workspaces/{owner_ws}/security-log",
    ]:
        r = client.get(path, headers=maya)
        assert r.status_code in (403, 404), f"GET {path} as a non-member should be denied, got {r.status_code}"

    # And the reverse direction, for good measure.
    r = client.get(f"/api/workspaces/{maya_ws}", headers=owner)
    assert r.status_code in (403, 404)
