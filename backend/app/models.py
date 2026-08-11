import uuid
import datetime as dt

from sqlalchemy import (
    Column, String, Float, ForeignKey, DateTime, Enum as SAEnum, UniqueConstraint
)
from sqlalchemy.orm import relationship

from .database import Base
import enum


def short_id():
    return uuid.uuid4().hex[:10]


class SplitType(str, enum.Enum):
    equal = "equal"
    percentage = "percentage"
    exact = "exact"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=short_id)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    trips = relationship("Trip", back_populates="owner")


class Trip(Base):
    __tablename__ = "trips"

    id = Column(String, primary_key=True, default=short_id)
    name = Column(String, nullable=False)
    # edit_token: full read/write access (the "SHARE" link)
    # view_token: read-only access (the "VIEW ONLY" link)
    edit_token = Column(String, unique=True, index=True, default=short_id)
    view_token = Column(String, unique=True, index=True, default=short_id)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    # Optional: set when a trip is created while logged in. NULL for
    # anonymous/shared trips, which keep working exactly as before via
    # edit_token/view_token regardless of this column.
    owner_id = Column(String, ForeignKey("users.id"), nullable=True)

    members = relationship("Member", back_populates="trip", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="trip", cascade="all, delete-orphan")
    owner = relationship("User", back_populates="trips")


class Member(Base):
    __tablename__ = "members"

    id = Column(String, primary_key=True, default=short_id)
    trip_id = Column(String, ForeignKey("trips.id"), nullable=False)
    name = Column(String, nullable=False)
    # Maintained on every expense write (add/delete) instead of recomputed on
    # every read. paid_by gets +amount, each participant gets -share.
    net_balance = Column(Float, nullable=False, default=0.0)

    trip = relationship("Trip", back_populates="members")
    shares = relationship("ExpenseShare", back_populates="member", cascade="all, delete-orphan")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(String, primary_key=True, default=short_id)
    trip_id = Column(String, ForeignKey("trips.id"), nullable=False)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    paid_by_id = Column(String, ForeignKey("members.id"), nullable=False)
    split_type = Column(SAEnum(SplitType), default=SplitType.equal)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    # Optional client-supplied key (e.g. Idempotency-Key header) used to make
    # retried/double-clicked "add expense" submits safe. Unique per trip.
    idempotency_key = Column(String, nullable=True)

    trip = relationship("Trip", back_populates="expenses")
    paid_by = relationship("Member", foreign_keys=[paid_by_id])
    shares = relationship("ExpenseShare", back_populates="expense", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("trip_id", "idempotency_key", name="uq_expense_trip_idempotency_key"),
    )


class ExpenseShare(Base):
    """How much of a given expense a member is responsible for."""
    __tablename__ = "expense_shares"

    id = Column(String, primary_key=True, default=short_id)
    expense_id = Column(String, ForeignKey("expenses.id"), nullable=False)
    member_id = Column(String, ForeignKey("members.id"), nullable=False)
    amount = Column(Float, nullable=False)  # resolved rupee amount owed for this expense

    expense = relationship("Expense", back_populates="shares")
    member = relationship("Member", back_populates="shares")
