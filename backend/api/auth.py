"""
JWT auth utilities and /auth endpoints.

Tokens carry: sub (user_id), name, is_commissioner.
Expiry: JWT_EXPIRY_DAYS days (long-lived for mobile use).
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRY_DAYS
from db import get_db

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ------------------------------------------------------------------ #
# Pydantic models
# ------------------------------------------------------------------ #

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    name: str
    is_commissioner: bool


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    is_commissioner: bool


# ------------------------------------------------------------------ #
# JWT helpers (used by deps.py)
# ------------------------------------------------------------------ #

def create_access_token(user: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS)
    payload = {
        "sub": user["id"],
        "name": user["name"],
        "is_commissioner": user["is_commissioner"],
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ------------------------------------------------------------------ #
# Endpoints
# ------------------------------------------------------------------ #

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest):
    db = get_db()
    existing = await db.table("users").select("id").eq("email", body.email).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="Email already registered")

    result = await db.table("users").insert({
        "name": body.name,
        "email": body.email,
        "hashed_password": hash_password(body.password),
        "is_commissioner": False,
    }).execute()
    user = result.data[0]
    return TokenResponse(
        access_token=create_access_token(user),
        user_id=user["id"],
        name=user["name"],
        is_commissioner=user["is_commissioner"],
    )


@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    db = get_db()
    result = await db.table("users").select("*").eq("email", form.username).execute()
    user = result.data[0] if result.data else None
    if not user or not verify_password(form.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return TokenResponse(
        access_token=create_access_token(user),
        user_id=user["id"],
        name=user["name"],
        is_commissioner=user["is_commissioner"],
    )


@router.get("/me", response_model=UserResponse)
async def me(token: str = Depends(oauth2_scheme)):
    from api.deps import get_current_user  # local import avoids circular at module level
    user = await get_current_user(token)
    return user
