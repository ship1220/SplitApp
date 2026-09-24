from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas, crud, models
from ..database import get_db
from ..utils.auth import get_current_user

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("", response_model=schemas.UserOut)
def my_profile(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.get("/trips", response_model=List[schemas.MyTripOut])
def my_trips(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    trips = crud.get_trips_by_owner(db, current_user.id)
    out = []
    for trip in trips:
        _, _, total_spend = crud.compute_balances(db, trip)
        out.append(
            schemas.MyTripOut(
                id=trip.id,
                name=trip.name,
                edit_token=trip.edit_token,
                view_token=trip.view_token,
                created_at=trip.created_at,
                member_count=len(trip.members),
                total_spend=total_spend,
            )
        )
    return out


@router.get("/stats", response_model=schemas.MyStatsOut)
def my_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_user_stats(db, current_user.id)
