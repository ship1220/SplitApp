"""
Core settlement math for the trip-splitting app.

Two independent pieces:
1. resolve_shares() - given an expense's split_type + raw participant input,
   figure out exactly how much rupee-amount each participant owes for THAT expense.
2. simplify_transfers() - given each member's net balance (paid - share),
   compute the minimum set of payments that clears all debts, using a
   greedy two-pointer match between the biggest debtor and biggest creditor.
"""
from typing import List, Dict, Tuple

ROUND = 2


def resolve_shares(amount: float, split_type: str, participants: List[dict]) -> Dict[str, float]:
    """
    participants: list of {"member_id": str, "value": float|None}
    Returns {member_id: resolved_amount} summing to `amount` (rounding-safe:
    any leftover paise from rounding is dropped onto the last participant).
    """
    if not participants:
        raise ValueError("An expense needs at least one participant")

    n = len(participants)
    result: Dict[str, float] = {}

    if split_type == "equal":
        base = round(amount / n, ROUND)
        running = 0.0
        for i, p in enumerate(participants):
            if i == n - 1:
                result[p["member_id"]] = round(amount - running, ROUND)
            else:
                result[p["member_id"]] = base
                running += base

    elif split_type == "percentage":
        total_pct = sum((p.get("value") or 0) for p in participants)
        if round(total_pct, 4) != 100:
            raise ValueError(f"Percentages must add up to 100, got {total_pct}")
        running = 0.0
        for i, p in enumerate(participants):
            if i == n - 1:
                result[p["member_id"]] = round(amount - running, ROUND)
            else:
                share = round(amount * (p.get("value") or 0) / 100, ROUND)
                result[p["member_id"]] = share
                running += share

    elif split_type == "exact":
        total_exact = sum((p.get("value") or 0) for p in participants)
        if abs(round(total_exact, ROUND) - round(amount, ROUND)) > 0.01:
            raise ValueError(
                f"Exact amounts ({total_exact}) must add up to the total ({amount})"
            )
        for p in participants:
            result[p["member_id"]] = round(p.get("value") or 0, ROUND)

    else:
        raise ValueError(f"Unknown split_type: {split_type}")

    return result


def simplify_transfers(net_balances: Dict[str, float]) -> List[Tuple[str, str, float]]:
    """
    net_balances: {member_id: net}  (positive = owed money, negative = owes money)
    Returns a list of (from_member_id, to_member_id, amount) transfers that
    settles all debts in the minimum number of transactions.

    Algorithm: sort debtors (most negative first) and creditors (most positive
    first). Each iteration, settle min(|debtor|, creditor) between the two
    largest, advance whichever side reaches zero. Repeat until balanced.
    """
    EPS = 0.01

    debtors = sorted(
        [[m, -v] for m, v in net_balances.items() if v < -EPS],
        key=lambda x: -x[1],  # biggest debt first
    )
    creditors = sorted(
        [[m, v] for m, v in net_balances.items() if v > EPS],
        key=lambda x: -x[1],  # biggest credit first
    )

    transfers = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor_id, debt = debtors[i]
        creditor_id, credit = creditors[j]
        pay = round(min(debt, credit), ROUND)

        if pay > EPS:
            transfers.append((debtor_id, creditor_id, pay))

        debtors[i][1] = round(debt - pay, ROUND)
        creditors[j][1] = round(credit - pay, ROUND)

        if debtors[i][1] <= EPS:
            i += 1
        if creditors[j][1] <= EPS:
            j += 1

    return transfers
