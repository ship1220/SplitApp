from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from . import models, schemas
from .utils.auth import hash_password
from .utils.settlement import resolve_shares, simplify_transfers


# ---------- User / auth ----------

def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, email: str, password: str) -> models.User:
    user = models.User(email=email, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------- Trip ----------

def create_trip(
    db: Session, trip_in: schemas.TripCreate, owner_id: Optional[str] = None
) -> models.Trip:
    trip = models.Trip(name=trip_in.name, owner_id=owner_id)
    db.add(trip)
    db.flush()  # get trip.id before adding members
    for name in trip_in.member_names:
        db.add(models.Member(trip_id=trip.id, name=name.strip()))
    db.commit()
    db.refresh(trip)
    return trip


def get_trip_by_token(db: Session, token: str) -> Optional[models.Trip]:
    return (
        db.query(models.Trip)
        .filter((models.Trip.edit_token == token) | (models.Trip.view_token == token))
        .options(joinedload(models.Trip.members))
        .first()
    )


def is_edit_token(trip: models.Trip, token: str) -> bool:
    return trip.edit_token == token


def delete_trip(db: Session, trip: models.Trip) -> None:
    db.delete(trip)
    db.commit()


def add_member(db: Session, trip: models.Trip, name: str) -> models.Member:
    member = models.Member(trip_id=trip.id, name=name.strip())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


# ---------- Expense ----------

def get_expense_by_idempotency_key(
    db: Session, trip_id: str, idempotency_key: str
) -> Optional[models.Expense]:
    if not idempotency_key:
        return None
    return (
        db.query(models.Expense)
        .filter(
            models.Expense.trip_id == trip_id,
            models.Expense.idempotency_key == idempotency_key,
        )
        .options(joinedload(models.Expense.shares).joinedload(models.ExpenseShare.member))
        .first()
    )


def add_expense(
    db: Session,
    trip: models.Trip,
    exp_in: schemas.ExpenseCreate,
    idempotency_key: Optional[str] = None,
) -> models.Expense:
    # If a matching expense already exists for this trip, return it instead
    # of creating a duplicate (safe for retried/double-clicked submits).
    if idempotency_key:
        existing = get_expense_by_idempotency_key(db, trip.id, idempotency_key)
        if existing:
            return existing

    members_by_id = {m.id: m for m in trip.members}
    if exp_in.paid_by not in members_by_id:
        raise ValueError("paid_by is not a member of this trip")
    for p in exp_in.participants:
        if p.member_id not in members_by_id:
            raise ValueError(f"participant {p.member_id} is not a member of this trip")

    participants = [{"member_id": p.member_id, "value": p.value} for p in exp_in.participants]
    resolved = resolve_shares(exp_in.amount, exp_in.split_type, participants)

    try:
        expense = models.Expense(
            trip_id=trip.id,
            description=exp_in.description.strip(),
            amount=exp_in.amount,
            paid_by_id=exp_in.paid_by,
            split_type=exp_in.split_type,
            idempotency_key=idempotency_key,
        )
        db.add(expense)
        db.flush()  # get expense.id before adding shares

        for member_id, amount in resolved.items():
            db.add(models.ExpenseShare(expense_id=expense.id, member_id=member_id, amount=amount))

        # Keep Member.net_balance in sync within the same transaction:
        # paid_by gets +amount, each participant gets -their resolved share.
        members_by_id[exp_in.paid_by].net_balance = round(
            members_by_id[exp_in.paid_by].net_balance + exp_in.amount, 2
        )
        for member_id, amount in resolved.items():
            members_by_id[member_id].net_balance = round(
                members_by_id[member_id].net_balance - amount, 2
            )

        db.commit()
    except IntegrityError:
        # Most likely a race: two requests with the same idempotency key
        # committed concurrently. Roll back and return the winner's row.
        db.rollback()
        if idempotency_key:
            existing = get_expense_by_idempotency_key(db, trip.id, idempotency_key)
            if existing:
                return existing
        raise
    except Exception:
        db.rollback()
        raise

    db.refresh(expense)
    return expense


def list_expenses(db: Session, trip_id: str) -> List[models.Expense]:
    return (
        db.query(models.Expense)
        .filter(models.Expense.trip_id == trip_id)
        .options(joinedload(models.Expense.shares).joinedload(models.ExpenseShare.member))
        .order_by(models.Expense.created_at.desc())
        .all()
    )


def delete_expense(db: Session, trip: models.Trip, expense_id: str) -> bool:
    expense = (
        db.query(models.Expense)
        .filter(models.Expense.id == expense_id, models.Expense.trip_id == trip.id)
        .options(joinedload(models.Expense.shares))
        .first()
    )
    if not expense:
        return False

    members_by_id = {m.id: m for m in trip.members}

    try:
        # Reverse the balance effect this expense had: paid_by loses -amount,
        # each participant gets back +their resolved share.
        payer = members_by_id.get(expense.paid_by_id)
        if payer is not None:
            payer.net_balance = round(payer.net_balance - expense.amount, 2)
        for s in expense.shares:
            member = members_by_id.get(s.member_id)
            if member is not None:
                member.net_balance = round(member.net_balance + s.amount, 2)

        db.delete(expense)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True


def update_expense(
    db: Session, trip: models.Trip, expense_id: str, exp_in: schemas.ExpenseCreate
) -> Optional[models.Expense]:
    """Replace an expense and atomically keep cached member balances in sync."""
    expense = (
        db.query(models.Expense)
        .filter(models.Expense.id == expense_id, models.Expense.trip_id == trip.id)
        .options(joinedload(models.Expense.shares))
        .first()
    )
    if not expense:
        return None

    members_by_id = {member.id: member for member in trip.members}
    if exp_in.paid_by not in members_by_id:
        raise ValueError("paid_by is not a member of this trip")
    for participant in exp_in.participants:
        if participant.member_id not in members_by_id:
            raise ValueError(f"participant {participant.member_id} is not a member of this trip")

    participants = [
        {"member_id": participant.member_id, "value": participant.value}
        for participant in exp_in.participants
    ]
    resolved = resolve_shares(exp_in.amount, exp_in.split_type, participants)

    updated_expense_id = expense.id
    try:
        # First undo the expense as it was previously recorded.
        old_payer = members_by_id[expense.paid_by_id]
        old_payer.net_balance = round(old_payer.net_balance - expense.amount, 2)
        for share in expense.shares:
            members_by_id[share.member_id].net_balance = round(
                members_by_id[share.member_id].net_balance + share.amount, 2
            )

        # Then apply the replacement values and shares.
        expense.description = exp_in.description.strip()
        expense.amount = exp_in.amount
        expense.paid_by_id = exp_in.paid_by
        expense.split_type = exp_in.split_type
        for share in list(expense.shares):
            db.delete(share)
        db.flush()
        for member_id, amount in resolved.items():
            db.add(models.ExpenseShare(expense_id=expense.id, member_id=member_id, amount=amount))

        members_by_id[exp_in.paid_by].net_balance = round(
            members_by_id[exp_in.paid_by].net_balance + exp_in.amount, 2
        )
        for member_id, amount in resolved.items():
            members_by_id[member_id].net_balance = round(
                members_by_id[member_id].net_balance - amount, 2
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return (
        db.query(models.Expense)
        .filter(models.Expense.id == updated_expense_id)
        .options(joinedload(models.Expense.paid_by), joinedload(models.Expense.shares).joinedload(models.ExpenseShare.member))
        .first()
    )


# ---------- Balances / Settlement ----------

def compute_balances(db: Session, trip: models.Trip):
    """
    Reads each member's maintained net_balance instead of re-summing every
    expense on every call. total_paid/total_share are still derived from the
    expense list (cheap, and needed for the per-member breakdown in the UI);
    only `net` (and therefore the settlement transfers) comes from the
    cached balance.
    """
    members = {m.id: m.name for m in trip.members}
    net_by_id = {m.id: m.net_balance for m in trip.members}
    paid = {mid: 0.0 for mid in members}
    shared = {mid: 0.0 for mid in members}

    expenses = list_expenses(db, trip.id)
    for exp in expenses:
        paid[exp.paid_by_id] = round(paid.get(exp.paid_by_id, 0.0) + exp.amount, 2)
        for s in exp.shares:
            shared[s.member_id] = round(shared.get(s.member_id, 0.0) + s.amount, 2)

    balances = []
    net_map = {}
    for mid, name in members.items():
        net = net_by_id.get(mid, 0.0)
        net_map[mid] = net
        balances.append(
            schemas.BalanceOut(
                member_id=mid, name=name,
                total_paid=paid.get(mid, 0.0),
                total_share=shared.get(mid, 0.0),
                net=net,
            )
        )

    transfers_raw = simplify_transfers(net_map)
    transfers = [
        schemas.TransferOut(
            from_id=f, from_name=members[f],
            to_id=t, to_name=members[t],
            amount=amt,
        )
        for f, t, amt in transfers_raw
    ]

    total_spend = round(sum(paid.values()), 2)
    return balances, transfers, total_spend


# ---------- "My trips" (logged-in users only) ----------

def get_trips_by_owner(db: Session, owner_id: str) -> List[models.Trip]:
    return (
        db.query(models.Trip)
        .filter(models.Trip.owner_id == owner_id)
        .options(joinedload(models.Trip.members))
        .order_by(models.Trip.created_at.desc())
        .all()
    )


def get_user_stats(db: Session, owner_id: str) -> schemas.MyStatsOut:
    """
    One aggregation query: sum of expense amounts per trip owned by the
    user. Deliberately simple — sums Expense.amount grouped by trip rather
    than trying to map individual Members back to this User account (no
    such link exists in this model, and the task explicitly says not to
    over-model that).
    """
    rows = (
        db.query(
            models.Trip.id,
            models.Trip.name,
            func.coalesce(func.sum(models.Expense.amount), 0.0),
        )
        .outerjoin(models.Expense, models.Expense.trip_id == models.Trip.id)
        .filter(models.Trip.owner_id == owner_id)
        .group_by(models.Trip.id, models.Trip.name)
        .order_by(models.Trip.name)
        .all()
    )

    trips = [
        schemas.TripSpendOut(trip_id=tid, trip_name=name, total_spend=round(total, 2))
        for tid, name, total in rows
    ]
    return schemas.MyStatsOut(
        total_spend=round(sum(t.total_spend for t in trips), 2),
        trip_count=len(trips),
        trips=trips,
    )
