from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .. import schemas, crud
from ..database import get_db
from .trips import _get_trip_or_404, _require_edit  # reuse shared helpers

router = APIRouter(prefix="/api/trips", tags=["expenses"])


@router.post("/{token}/expenses", response_model=schemas.ExpenseOut)
def add_expense(
    token: str,
    expense_in: schemas.ExpenseCreate,
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    trip = _get_trip_or_404(db, token)
    _require_edit(trip, token)
    try:
        expense = crud.add_expense(db, trip, expense_in, idempotency_key=idempotency_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return schemas.ExpenseOut(
        id=expense.id,
        description=expense.description,
        amount=expense.amount,
        paid_by=expense.paid_by_id,
        paid_by_name=expense.paid_by.name,
        split_type=expense.split_type.value if hasattr(expense.split_type, "value") else expense.split_type,
        created_at=expense.created_at,
        shares=[
            schemas.ExpenseShareOut(
                member_id=s.member_id, member_name=s.member.name, amount=s.amount
            )
            for s in expense.shares
        ],
    )


@router.delete("/{token}/expenses/{expense_id}")
def delete_expense(token: str, expense_id: str, db: Session = Depends(get_db)):
    trip = _get_trip_or_404(db, token)
    _require_edit(trip, token)
    ok = crud.delete_expense(db, trip, expense_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"ok": True}


@router.put("/{token}/expenses/{expense_id}", response_model=schemas.ExpenseOut)
def update_expense(
    token: str, expense_id: str, expense_in: schemas.ExpenseCreate, db: Session = Depends(get_db)
):
    trip = _get_trip_or_404(db, token)
    _require_edit(trip, token)
    try:
        expense = crud.update_expense(db, trip, expense_id, expense_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return schemas.ExpenseOut(
        id=expense.id, description=expense.description, amount=expense.amount,
        paid_by=expense.paid_by_id, paid_by_name=expense.paid_by.name,
        split_type=expense.split_type.value if hasattr(expense.split_type, "value") else expense.split_type,
        created_at=expense.created_at,
        shares=[schemas.ExpenseShareOut(member_id=s.member_id, member_name=s.member.name, amount=s.amount) for s in expense.shares],
    )
