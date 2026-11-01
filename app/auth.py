"""Authentication utilities: JWT tokens, password hashing, and FastAPI dependencies."""

import os
import bcrypt
from datetime import datetime, timedelta

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .database import get_db
from .models import User

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_SECRET = "parkwise-dev-secret-change-me"

JWT_SECRET: str = os.getenv("JWT_SECRET", "")
if not JWT_SECRET:
    JWT_SECRET = _DEFAULT_SECRET
    print(
        "WARNING: JWT_SECRET is not set. "
        "Using an insecure default – do NOT use this in production!"
    )

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return *True* if *plain_password* matches *hashed_password*."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def hash_password(password: str) -> str:
    """Return the bcrypt hash of *password*."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_access_token(data: dict) -> str:
    """Create a signed JWT containing *data* with an expiration claim."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the JWT from the Authorization header or cookie.

    Returns the corresponding :class:`User` instance or raises **401**.
    """
    token: str | None = None

    # Prefer the Authorization header, fall back to the cookie.
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif access_token:
        token = access_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: int | None = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(User, int(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency that permits only users with the **ADMIN** role."""
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return current_user


def require_customer(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency that permits only users with the **CUSTOMER** role."""
    if current_user.role != "CUSTOMER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer access required.",
        )
    return current_user
