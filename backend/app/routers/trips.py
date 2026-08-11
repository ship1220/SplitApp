from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import schemas, crud, models
from ..database import get_db
from ..utils.auth import get_current_user_optional

router = APIRouter(prefix="/api/trips", tags=["trips"])


def _get_trip_or_404(db: Session, token: str):
    trip = crud.get_trip_by_token(db, token)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found. Check your link.")
    return trip


def _require_edit(trip, token: str):
    if not crud.is_edit_token(trip, token):
        raise HTTPException(status_code=403, detail="This is a view-only link.")


def _serialize_detail(db: Session, trip) -> schemas.TripDetailOut:
    balances, transfers, total_spend = crud.compute_balances(db, trip)
    expenses = crud.list_expenses(db, trip.id)
    expense_out = [
        schemas.ExpenseOut(
            id=e.id,
            description=e.description,
            amount=e.amount,
            paid_by=e.paid_by_id,
            paid_by_name=e.paid_by.name,
            split_type=e.split_type.value if hasattr(e.split_type, "value") else e.split_type,
            created_at=e.created_at,
            shares=[
                schemas.ExpenseShareOut(
                    member_id=s.member_id, member_name=s.member.name, amount=s.amount
                )
                for s in e.shares
            ],
        )
        for e in expenses
    ]
    return schemas.TripDetailOut(
        id=trip.id,
        name=trip.name,
        edit_token=trip.edit_token,
        view_token=trip.view_token,
        members=[schemas.MemberOut.model_validate(m) for m in trip.members],
        expenses=expense_out,
        total_spend=total_spend,
        balances=balances,
        transfers=transfers,
    )


@router.post("", response_model=schemas.TripOut)
def create_trip(
    trip_in: schemas.TripCreate,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_current_user_optional),
):
    # Anonymous requests (no/invalid Authorization header) get owner_id=None,
    # exactly as before — this endpoint's anonymous behavior is unchanged.
    owner_id = current_user.id if current_user else None
    trip = crud.create_trip(db, trip_in, owner_id=owner_id)
    return trip


@router.get("/{token}", response_model=schemas.TripDetailOut)
def get_trip(token: str, db: Session = Depends(get_db)):
    trip = _get_trip_or_404(db, token)
    return _serialize_detail(db, trip)


@router.post("/{token}/members", response_model=schemas.MemberOut)
def add_member(token: str, member_in: schemas.MemberCreate, db: Session = Depends(get_db)):
    trip = _get_trip_or_404(db, token)
    _require_edit(trip, token)
    return crud.add_member(db, trip, member_in.name)


@router.delete("/{token}")
def delete_trip(token: str, db: Session = Depends(get_db)):
    # Same permission model as every other write on a trip: whoever holds
    # the edit_token (the "SHARE" link) can delete it — same as an
    # anonymous collaborator can already add/remove members and expenses.
    # This is intentionally the token check, not an owner/login check, so
    # anonymous trips can still be deleted by whoever has the link.
    trip = _get_trip_or_404(db, token)
    _require_edit(trip, token)
    crud.delete_trip(db, trip)
    return {"ok": True}
