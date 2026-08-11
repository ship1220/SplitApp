"""
Integration tests hitting the real FastAPI app + a throwaway SQLite DB
per test (see conftest.py). Covers the create-trip -> add-expense -> balances
flow, view-token read-only enforcement, and idempotency-key deduplication.
"""


def member_id(trip_json, name):
    return next(m["id"] for m in trip_json["members"] if m["name"] == name)


# ---------- create trip -> add expense -> balances ----------

def test_create_trip_returns_edit_and_view_tokens(client):
    res = client.post("/api/trips", json={"name": "Weekend", "member_names": ["A", "B"]})
    assert res.status_code == 200
    body = res.json()
    assert body["edit_token"]
    assert body["view_token"]
    assert body["edit_token"] != body["view_token"]
    assert len(body["members"]) == 2


def test_equal_split_expense_updates_balances_correctly(client, trip):
    edit_token = trip["edit_token"]
    alice, bob, carol = (member_id(trip, n) for n in ("Alice", "Bob", "Carol"))

    res = client.post(f"/api/trips/{edit_token}/expenses", json={
        "description": "Dinner",
        "amount": 90.0,
        "paid_by": alice,
        "split_type": "equal",
        "participants": [{"member_id": alice}, {"member_id": bob}, {"member_id": carol}],
    })
    assert res.status_code == 200

    detail = client.get(f"/api/trips/{edit_token}").json()
    balances = {b["member_id"]: b["net"] for b in detail["balances"]}

    assert balances[alice] == 60.0   # paid 90, owes 30
    assert balances[bob] == -30.0
    assert balances[carol] == -30.0
    assert detail["total_spend"] == 90.0

    # settlement should net out to zero total movement in either direction
    transfer_total = round(sum(t["amount"] for t in detail["transfers"]), 2)
    assert transfer_total == 60.0


def test_deleting_expense_reverses_balances_back_to_zero(client, trip):
    edit_token = trip["edit_token"]
    alice, bob, carol = (member_id(trip, n) for n in ("Alice", "Bob", "Carol"))

    res = client.post(f"/api/trips/{edit_token}/expenses", json={
        "description": "Taxi",
        "amount": 30.0,
        "paid_by": bob,
        "split_type": "equal",
        "participants": [{"member_id": alice}, {"member_id": bob}, {"member_id": carol}],
    })
    expense_id = res.json()["id"]

    del_res = client.delete(f"/api/trips/{edit_token}/expenses/{expense_id}")
    assert del_res.status_code == 200

    detail = client.get(f"/api/trips/{edit_token}").json()
    assert detail["expenses"] == []
    for b in detail["balances"]:
        assert b["net"] == 0.0


def test_percentage_and_exact_splits_produce_correct_balances(client, trip):
    edit_token = trip["edit_token"]
    alice, bob, carol = (member_id(trip, n) for n in ("Alice", "Bob", "Carol"))

    client.post(f"/api/trips/{edit_token}/expenses", json={
        "description": "Hotel",
        "amount": 300.0,
        "paid_by": alice,
        "split_type": "percentage",
        "participants": [
            {"member_id": alice, "value": 50},
            {"member_id": bob, "value": 30},
            {"member_id": carol, "value": 20},
        ],
    })
    client.post(f"/api/trips/{edit_token}/expenses", json={
        "description": "Groceries",
        "amount": 50.0,
        "paid_by": carol,
        "split_type": "exact",
        "participants": [
            {"member_id": alice, "value": 20.0},
            {"member_id": bob, "value": 30.0},
        ],
    })

    detail = client.get(f"/api/trips/{edit_token}").json()
    balances = {b["member_id"]: b["net"] for b in detail["balances"]}

    # alice: paid 300, owes 150 (pct) + 20 (exact) = 170 -> net +130
    assert balances[alice] == 130.0
    # bob: paid 0, owes 90 (pct) + 30 (exact) = 120 -> net -120
    assert balances[bob] == -120.0
    # carol: paid 50, owes 60 (pct) + 0 -> net -10
    assert balances[carol] == -10.0
    assert round(sum(balances.values()), 2) == 0.0


# ---------- view-token read-only enforcement ----------

def test_view_token_can_read_trip(client, trip):
    res = client.get(f"/api/trips/{trip['view_token']}")
    assert res.status_code == 200
    assert res.json()["id"] == trip["id"]


def test_view_token_forbidden_on_add_expense(client, trip):
    view_token = trip["view_token"]
    alice = member_id(trip, "Alice")
    res = client.post(f"/api/trips/{view_token}/expenses", json={
        "description": "Snacks",
        "amount": 10.0,
        "paid_by": alice,
        "split_type": "equal",
        "participants": [{"member_id": alice}],
    })
    assert res.status_code == 403


def test_view_token_forbidden_on_delete_expense(client, trip):
    edit_token = trip["edit_token"]
    view_token = trip["view_token"]
    alice = member_id(trip, "Alice")

    add_res = client.post(f"/api/trips/{edit_token}/expenses", json={
        "description": "Snacks",
        "amount": 10.0,
        "paid_by": alice,
        "split_type": "equal",
        "participants": [{"member_id": alice}],
    })
    expense_id = add_res.json()["id"]

    del_res = client.delete(f"/api/trips/{view_token}/expenses/{expense_id}")
    assert del_res.status_code == 403


def test_view_token_forbidden_on_add_member(client, trip):
    res = client.post(f"/api/trips/{trip['view_token']}/members", json={"name": "Dave"})
    assert res.status_code == 403


def test_unknown_token_returns_404(client):
    res = client.get("/api/trips/does-not-exist")
    assert res.status_code == 404


# ---------- idempotency ----------

def test_duplicate_idempotency_key_returns_same_expense(client, trip):
    edit_token = trip["edit_token"]
    alice = member_id(trip, "Alice")
    payload = {
        "description": "Coffee",
        "amount": 12.0,
        "paid_by": alice,
        "split_type": "equal",
        "participants": [{"member_id": alice}],
    }
    headers = {"Idempotency-Key": "retry-key-123"}

    first = client.post(f"/api/trips/{edit_token}/expenses", json=payload, headers=headers)
    second = client.post(f"/api/trips/{edit_token}/expenses", json=payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    detail = client.get(f"/api/trips/{edit_token}").json()
    assert len(detail["expenses"]) == 1  # no duplicate row created

    # and balances only reflect a single application of the expense
    alice_balance = next(b["net"] for b in detail["balances"] if b["member_id"] == alice)
    assert alice_balance == 0.0  # paid 12, owes 12 (sole participant)


def test_different_idempotency_keys_create_separate_expenses(client, trip):
    edit_token = trip["edit_token"]
    alice = member_id(trip, "Alice")
    payload = {
        "description": "Coffee",
        "amount": 12.0,
        "paid_by": alice,
        "split_type": "equal",
        "participants": [{"member_id": alice}],
    }

    client.post(f"/api/trips/{edit_token}/expenses", json=payload,
                headers={"Idempotency-Key": "key-a"})
    client.post(f"/api/trips/{edit_token}/expenses", json=payload,
                headers={"Idempotency-Key": "key-b"})

    detail = client.get(f"/api/trips/{edit_token}").json()
    assert len(detail["expenses"]) == 2


def test_missing_idempotency_key_still_works(client, trip):
    edit_token = trip["edit_token"]
    alice = member_id(trip, "Alice")
    res = client.post(f"/api/trips/{edit_token}/expenses", json={
        "description": "No key",
        "amount": 5.0,
        "paid_by": alice,
        "split_type": "equal",
        "participants": [{"member_id": alice}],
    })
    assert res.status_code == 200
