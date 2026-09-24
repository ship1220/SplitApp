"""
Unit tests for utils/settlement.py — pure functions, no DB involved.

Covers resolve_shares() (equal / percentage / exact, rounding edge cases,
invalid totals) and simplify_transfers() (balanced groups, lopsided
debtor/creditor counts, near-zero float edges).
"""
import pytest

from app.utils.settlement import resolve_shares, simplify_transfers


# ---------- resolve_shares: equal ----------

def test_equal_split_divides_evenly():
    result = resolve_shares(90.0, "equal", [
        {"member_id": "a", "value": None},
        {"member_id": "b", "value": None},
        {"member_id": "c", "value": None},
    ])
    assert result == {"a": 30.0, "b": 30.0, "c": 30.0}
    assert round(sum(result.values()), 2) == 90.0


def test_equal_split_dumps_rounding_remainder_on_last_participant():
    # 100 / 3 = 33.333... -> 33.33, 33.33, and the remainder on the last one
    result = resolve_shares(100.0, "equal", [
        {"member_id": "a", "value": None},
        {"member_id": "b", "value": None},
        {"member_id": "c", "value": None},
    ])
    assert result["a"] == 33.33
    assert result["b"] == 33.33
    assert result["c"] == 33.34
    assert round(sum(result.values()), 2) == 100.0


def test_equal_split_single_participant_gets_full_amount():
    result = resolve_shares(45.5, "equal", [{"member_id": "a", "value": None}])
    assert result == {"a": 45.5}


def test_equal_split_no_participants_raises():
    with pytest.raises(ValueError):
        resolve_shares(50.0, "equal", [])


# ---------- resolve_shares: percentage ----------

def test_percentage_split_basic():
    result = resolve_shares(200.0, "percentage", [
        {"member_id": "a", "value": 25},
        {"member_id": "b", "value": 75},
    ])
    assert result == {"a": 50.0, "b": 150.0}
    assert round(sum(result.values()), 2) == 200.0


def test_percentage_split_must_total_100():
    with pytest.raises(ValueError):
        resolve_shares(100.0, "percentage", [
            {"member_id": "a", "value": 50},
            {"member_id": "b", "value": 40},
        ])


def test_percentage_split_rounding_remainder_on_last_participant():
    # thirds: 33.333...% each, should still sum exactly to the total
    result = resolve_shares(100.0, "percentage", [
        {"member_id": "a", "value": 33.34},
        {"member_id": "b", "value": 33.33},
        {"member_id": "c", "value": 33.33},
    ])
    assert round(sum(result.values()), 2) == 100.0


def test_percentage_split_missing_value_treated_as_zero():
    result = resolve_shares(100.0, "percentage", [
        {"member_id": "a", "value": 100},
        {"member_id": "b", "value": None},
    ])
    assert result["b"] == 0.0
    assert round(sum(result.values()), 2) == 100.0


# ---------- resolve_shares: exact ----------

def test_exact_split_basic():
    result = resolve_shares(100.0, "exact", [
        {"member_id": "a", "value": 60.0},
        {"member_id": "b", "value": 40.0},
    ])
    assert result == {"a": 60.0, "b": 40.0}


def test_exact_split_must_sum_to_total():
    with pytest.raises(ValueError):
        resolve_shares(100.0, "exact", [
            {"member_id": "a", "value": 60.0},
            {"member_id": "b", "value": 30.0},
        ])


def test_exact_split_allows_penny_rounding_slack():
    # within the 0.01 tolerance baked into resolve_shares
    result = resolve_shares(100.0, "exact", [
        {"member_id": "a", "value": 60.005},
        {"member_id": "b", "value": 39.995},
    ])
    assert result["a"] == 60.01 or result["a"] == 60.0  # rounds to 2dp either way
    assert round(sum(result.values()), 2) == pytest.approx(100.0, abs=0.02)


# ---------- resolve_shares: invalid split_type ----------

def test_unknown_split_type_raises():
    with pytest.raises(ValueError):
        resolve_shares(50.0, "not_a_real_type", [{"member_id": "a", "value": None}])


# ---------- simplify_transfers ----------

def test_simplify_transfers_two_person_balanced():
    transfers = simplify_transfers({"a": -50.0, "b": 50.0})
    assert transfers == [("a", "b", 50.0)]


def test_simplify_transfers_already_settled_no_transfers():
    transfers = simplify_transfers({"a": 0.0, "b": 0.0, "c": 0.0})
    assert transfers == []


def test_simplify_transfers_one_debtor_many_creditors():
    # a owes everyone; b, c, d are each owed a slice
    net = {"a": -60.0, "b": 20.0, "c": 20.0, "d": 20.0}
    transfers = simplify_transfers(net)
    assert len(transfers) == 3
    assert all(f == "a" for f, _, _ in transfers)
    assert round(sum(amt for _, _, amt in transfers), 2) == 60.0


def test_simplify_transfers_many_debtors_one_creditor():
    net = {"a": -10.0, "b": -20.0, "c": -30.0, "d": 60.0}
    transfers = simplify_transfers(net)
    assert len(transfers) == 3
    assert all(t == "d" for _, t, _ in transfers)
    assert round(sum(amt for _, _, amt in transfers), 2) == 60.0


def test_simplify_transfers_uses_minimum_number_of_transactions():
    # classic case: 3 people, should resolve in 2 transfers not 3
    net = {"a": -30.0, "b": -20.0, "c": 50.0}
    transfers = simplify_transfers(net)
    assert len(transfers) == 2


def test_simplify_transfers_near_zero_balances_ignored():
    # sub-cent noise from float math shouldn't produce a transfer
    net = {"a": -0.004, "b": 0.004, "c": 0.0}
    transfers = simplify_transfers(net)
    assert transfers == []


def test_simplify_transfers_total_amount_conserved():
    net = {"a": -15.5, "b": -24.5, "c": 10.0, "d": 30.0}
    transfers = simplify_transfers(net)
    total_paid = round(sum(amt for _, _, amt in transfers), 2)
    assert total_paid == 40.0
