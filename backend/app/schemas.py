from typing import List, Optional, Literal
from pydantic import BaseModel, EmailStr, Field
import datetime as dt


# ---------- Auth ----------

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    created_at: dt.datetime

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Trip ----------

class TripCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    member_names: List[str] = Field(..., min_items=1)


class MemberOut(BaseModel):
    id: str
    name: str

    class Config:
        from_attributes = True


class TripOut(BaseModel):
    id: str
    name: str
    edit_token: str
    view_token: str
    members: List[MemberOut]

    class Config:
        from_attributes = True


class MemberCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)


# ---------- Expense ----------

class SplitInput(BaseModel):
    member_id: str
    # for split_type=equal this is ignored, may be omitted
    # for percentage: 0-100
    # for exact: rupee amount
    value: Optional[float] = None


class ExpenseCreate(BaseModel):
    description: str = Field(..., min_length=1, max_length=120)
    amount: float = Field(..., gt=0)
    paid_by: str
    split_type: Literal["equal", "percentage", "exact"] = "equal"
    participants: List[SplitInput]  # who shares this expense (and optional custom value)


class ExpenseShareOut(BaseModel):
    member_id: str
    member_name: str
    amount: float

    class Config:
        from_attributes = True


class ExpenseOut(BaseModel):
    id: str
    description: str
    amount: float
    paid_by: str
    paid_by_name: str
    split_type: str
    created_at: dt.datetime
    shares: List[ExpenseShareOut]

    class Config:
        from_attributes = True


# ---------- Balances / Settlement ----------

class BalanceOut(BaseModel):
    member_id: str
    name: str
    total_paid: float
    total_share: float
    net: float  # positive = owed money back, negative = owes money


class TransferOut(BaseModel):
    from_id: str
    from_name: str
    to_id: str
    to_name: str
    amount: float


class TripDetailOut(BaseModel):
    id: str
    name: str
    edit_token: str
    view_token: str
    members: List[MemberOut]
    expenses: List[ExpenseOut]
    total_spend: float
    balances: List[BalanceOut]
    transfers: List[TransferOut]


# ---------- "My trips" (logged-in users only) ----------

class MyTripOut(BaseModel):
    id: str
    name: str
    edit_token: str
    view_token: str
    created_at: dt.datetime
    member_count: int
    total_spend: float


class TripSpendOut(BaseModel):
    trip_id: str
    trip_name: str
    total_spend: float


class MyStatsOut(BaseModel):
    total_spend: float
    trip_count: int
    trips: List[TripSpendOut]
