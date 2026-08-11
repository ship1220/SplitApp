"""
Auth + "my trips"/"my stats" tests. Uses the same client/trip fixtures as
test_api.py (see conftest.py). Anonymous trip creation/access (no auth at
all) is exercised throughout test_api.py and is intentionally not touched
here — these tests only cover the new, additive user-account behavior.
"""
import pytest


def signup(client, email="alice@example.com", password="hunter2pass"):
    res = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- signup / login ----------

def test_signup_returns_token(client):
    token = signup(client)
    assert token


def test_signup_duplicate_email_rejected(client):
    signup(client, email="dup@example.com")
    res = client.post(
        "/api/auth/signup",
        json={"email": "dup@example.com", "password": "anotherpass1"},
    )
    assert res.status_code == 400


def test_login_with_correct_password_returns_token(client):
    signup(client, email="bob@example.com", password="correcthorse1")
    res = client.post(
        "/api/auth/login",
        json={"email": "bob@example.com", "password": "correcthorse1"},
    )
    assert res.status_code == 200
    assert res.json()["access_token"]


def test_login_with_wrong_password_rejected(client):
    signup(client, email="carol@example.com", password="rightpassword")
    res = client.post(
        "/api/auth/login",
        json={"email": "carol@example.com", "password": "wrongpassword"},
    )
    assert res.status_code == 401


def test_login_unknown_email_rejected(client):
    res = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "whatever123"},
    )
    assert res.status_code == 401


# ---------- protected routes ----------

def test_me_trips_rejects_missing_token(client):
    res = client.get("/api/me/trips")
    assert res.status_code == 401


def test_me_trips_rejects_invalid_token(client):
    res = client.get("/api/me/trips", headers=auth_headers("not-a-real-token"))
    assert res.status_code == 401


def test_me_stats_rejects_missing_token(client):
    res = client.get("/api/me/stats")
    assert res.status_code == 401


# ---------- /api/me/trips ----------

def test_me_trips_only_returns_owners_trips(client):
    token_a = signup(client, email="owner-a@example.com")
    token_b = signup(client, email="owner-b@example.com")

    client.post(
        "/api/trips",
        json={"name": "Alice's Trip", "member_names": ["A"]},
        headers=auth_headers(token_a),
    )
    client.post(
        "/api/trips",
        json={"name": "Bob's Trip", "member_names": ["B"]},
        headers=auth_headers(token_b),
    )
    # Anonymous trip (no Authorization header at all) — must not show up
    # for either logged-in user.
    client.post("/api/trips", json={"name": "Anon Trip", "member_names": ["X"]})

    res = client.get("/api/me/trips", headers=auth_headers(token_a))
    assert res.status_code == 200
    names = [t["name"] for t in res.json()]
    assert names == ["Alice's Trip"]


def test_anonymous_trip_creation_still_works_without_auth_header(client):
    res = client.post("/api/trips", json={"name": "No login needed", "member_names": ["A", "B"]})
    assert res.status_code == 200
    body = res.json()
    assert body["edit_token"]
    assert body["view_token"]


# ---------- /api/me/stats ----------

def test_me_stats_returns_correct_totals(client):
    token = signup(client, email="stats-user@example.com")
    headers = auth_headers(token)

    trip1 = client.post(
        "/api/trips",
        json={"name": "Trip One", "member_names": ["A", "B"]},
        headers=headers,
    ).json()
    trip2 = client.post(
        "/api/trips",
        json={"name": "Trip Two", "member_names": ["C"]},
        headers=headers,
    ).json()

    a_id = trip1["members"][0]["id"]
    c_id = trip2["members"][0]["id"]

    client.post(
        f"/api/trips/{trip1['edit_token']}/expenses",
        json={
            "description": "Lunch",
            "amount": 40.0,
            "paid_by": a_id,
            "split_type": "equal",
            "participants": [{"member_id": a_id}],
        },
    )
    client.post(
        f"/api/trips/{trip1['edit_token']}/expenses",
        json={
            "description": "Snacks",
            "amount": 10.0,
            "paid_by": a_id,
            "split_type": "equal",
            "participants": [{"member_id": a_id}],
        },
    )
    client.post(
        f"/api/trips/{trip2['edit_token']}/expenses",
        json={
            "description": "Coffee",
            "amount": 5.0,
            "paid_by": c_id,
            "split_type": "equal",
            "participants": [{"member_id": c_id}],
        },
    )

    res = client.get("/api/me/stats", headers=headers)
    assert res.status_code == 200
    body = res.json()

    assert body["trip_count"] == 2
    assert body["total_spend"] == 55.0

    by_name = {t["trip_name"]: t["total_spend"] for t in body["trips"]}
    assert by_name["Trip One"] == 50.0
    assert by_name["Trip Two"] == 5.0


def test_me_stats_empty_for_user_with_no_trips(client):
    token = signup(client, email="empty-user@example.com")
    res = client.get("/api/me/stats", headers=auth_headers(token))
    assert res.status_code == 200
    body = res.json()
    assert body["total_spend"] == 0.0
    assert body["trip_count"] == 0
    assert body["trips"] == []


# ---------- /api/me (profile) ----------

def test_me_profile_returns_email(client):
    token = signup(client, email="profile-user@example.com")
    res = client.get("/api/me", headers=auth_headers(token))
    assert res.status_code == 200
    assert res.json()["email"] == "profile-user@example.com"


def test_me_profile_rejects_missing_token(client):
    res = client.get("/api/me")
    assert res.status_code == 401


# ---------- delete trip ----------

def test_owner_can_delete_own_trip(client):
    token = signup(client, email="deleter@example.com")
    headers = auth_headers(token)

    trip = client.post(
        "/api/trips",
        json={"name": "Trip to delete", "member_names": ["A"]},
        headers=headers,
    ).json()

    del_res = client.delete(f"/api/trips/{trip['edit_token']}")
    assert del_res.status_code == 200

    # gone from the trip endpoint itself
    assert client.get(f"/api/trips/{trip['edit_token']}").status_code == 404

    # gone from "my trips" / stats too
    assert client.get("/api/me/trips", headers=headers).json() == []
    stats = client.get("/api/me/stats", headers=headers).json()
    assert stats["trip_count"] == 0
    assert stats["total_spend"] == 0.0


def test_anonymous_trip_can_still_be_deleted_via_edit_token(client, trip):
    edit_token = trip["edit_token"]
    del_res = client.delete(f"/api/trips/{edit_token}")
    assert del_res.status_code == 200
    assert client.get(f"/api/trips/{edit_token}").status_code == 404


def test_view_token_forbidden_on_delete_trip(client, trip):
    view_token = trip["view_token"]
    del_res = client.delete(f"/api/trips/{view_token}")
    assert del_res.status_code == 403
    # trip still exists via its edit token
    assert client.get(f"/api/trips/{trip['edit_token']}").status_code == 200


def test_delete_unknown_trip_returns_404(client):
    res = client.delete("/api/trips/not-a-real-token")
    assert res.status_code == 404
