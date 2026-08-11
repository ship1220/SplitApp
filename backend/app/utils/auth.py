"""
Auth helpers: password hashing (passlib/bcrypt) and JWT issuing/verification
(python-jose, HS256, 24h expiry). Deliberately minimal — no refresh tokens,
roles, or email verification. This is additive: nothing here is used by the
existing token-based (edit_token/view_token) trip routes, which don't call
get_current_user and keep working for anonymous users exactly as before.
"""
import os
import datetime as dt
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

# In production set JWT_SECRET to a long random value.
# The development fallback keeps local setup simple; Render should always
# provide JWT_SECRET as an environment variable.
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60  # 24h

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# auto_error=False so a missing token surfaces as our own 401 (with a clear
# detail message) instead of FastAPI's default.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str) -> str:
    expire = dt.datetime.utcnow() + dt.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise unauthorized
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise unauthorized
    except JWTError:
        raise unauthorized

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise unauthorized
    return user


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[models.User]:
    """
    Like get_current_user but never raises: no/invalid token just means
    "anonymous". Used only by POST /api/trips so a trip created while logged
    in gets owner_id set, while anonymous trip creation (no Authorization
    header at all) keeps working exactly as before.
    """
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None

    return db.query(models.User).filter(models.User.id == user_id).first()
