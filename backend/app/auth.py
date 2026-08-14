"""Google OAuth 2.0 + JWT session tokens for Skretch.

Flow:
  1. GET /auth/google  → redirect to Google consent screen
  2. Google redirects  → GET /auth/callback?code=...
  3. Exchange code → access_token → fetch userinfo → upsert User
  4. Sign a short-lived JWT, redirect frontend to /?token=<jwt>

The JWT payload is: { "sub": user.id, "email": user.email, "exp": ... }
"""

import os
import time
import logging
from typing import Optional
from urllib.parse import urlencode

import httpx
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from . import crud
from .database import get_db

logger = logging.getLogger("canvas.auth")

# ── Config (from environment) ─────────────────────────────────────────────────

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# NEVER commit a real secret; generate with: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET    = os.getenv("JWT_SECRET", "change-me-in-production-please")
JWT_ALGORITHM = "HS256"
JWT_TTL_SECS  = 60 * 60 * 24 * 30  # 30 days

GOOGLE_SCOPES = " ".join([
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/documents",   # required for Docs API create/batchUpdate
    "https://www.googleapis.com/auth/drive.file",  # so the doc shows up in the user's Drive
])

# ── Google OAuth helpers ──────────────────────────────────────────────────────

def build_google_auth_url() -> str:
    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         GOOGLE_SCOPES,
        "access_type":   "offline",
        "prompt":        "consent",   # force refresh_token on every login
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


async def exchange_code(code: str) -> dict:
    """Exchange an authorization code for Google tokens."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code":          code,
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri":  GOOGLE_REDIRECT_URI,
                "grant_type":    "authorization_code",
            },
        )
    resp.raise_for_status()
    return resp.json()


async def get_google_userinfo(access_token: str) -> dict:
    """Fetch the authenticated user's profile from Google."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    resp.raise_for_status()
    return resp.json()


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_jwt(user_id: str, email: str) -> str:
    payload = {
        "sub":   user_id,
        "email": email,
        "iat":   int(time.time()),
        "exp":   int(time.time()) + JWT_TTL_SECS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt(token: str) -> dict:
    """Decode and validate a JWT.  Raises HTTPException on failure."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
        )


# ── FastAPI dependency ────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
):
    """Return the authenticated User ORM object, or None if unauthenticated.

    Most endpoints treat auth as optional for now so the canvas still works
    without login during development.  Call `require_user()` for endpoints
    that need a guaranteed user.
    """
    if not credentials:
        return None
    payload = verify_jwt(credentials.credentials)
    user = crud.get_user(db, payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
):
    """Like get_current_user but raises 401 when unauthenticated."""
    user = get_current_user(credentials, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user
