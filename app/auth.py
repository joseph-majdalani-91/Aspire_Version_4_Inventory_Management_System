from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UserAccount, UserRole


@dataclass(frozen=True)
class Principal:
    user_id: int
    username: str
    full_name: str
    role: UserRole
    api_key: str


def _get_auth_password_pepper() -> str:
    pepper = os.getenv("AUTH_PASSWORD_PEPPER", "").strip()
    if not pepper:
        raise RuntimeError("AUTH_PASSWORD_PEPPER is required and must be non-empty")
    return pepper


def ensure_auth_config() -> None:
    _get_auth_password_pepper()


def _legacy_hash_password(raw_password: str) -> str:
    pepper = _get_auth_password_pepper()
    payload = f"{pepper}:{raw_password}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def hash_password(raw_password: str) -> str:
    pepper = _get_auth_password_pepper()
    iteration_env = os.getenv("AUTH_PASSWORD_ITERATIONS", "210000").strip()
    try:
        iterations = max(100_000, int(iteration_env))
    except ValueError as exc:
        raise RuntimeError("AUTH_PASSWORD_ITERATIONS must be an integer") from exc

    salt_hex = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        f"{pepper}:{raw_password}".encode("utf-8"),
        bytes.fromhex(salt_hex),
        iterations,
    ).hex()
    return f"pbkdf2_sha256${iterations}${salt_hex}${digest}"


def verify_password(raw_password: str, password_hash: str) -> bool:
    if password_hash.startswith("pbkdf2_sha256$"):
        parts = password_hash.split("$")
        if len(parts) != 4:
            return False
        _, iteration_str, salt_hex, expected_digest = parts
        try:
            iterations = int(iteration_str)
            salt = bytes.fromhex(salt_hex)
        except ValueError:
            return False

        candidate_digest = hashlib.pbkdf2_hmac(
            "sha256",
            f"{_get_auth_password_pepper()}:{raw_password}".encode("utf-8"),
            salt,
            iterations,
        ).hex()
        return hmac.compare_digest(candidate_digest, expected_digest)

    return hmac.compare_digest(_legacy_hash_password(raw_password), password_hash)


def get_current_principal(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Principal:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    user = db.scalar(
        select(UserAccount).where(UserAccount.api_key == x_api_key, UserAccount.is_active.is_(True))
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return Principal(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        api_key=user.api_key,
    )


def require_roles(*allowed_roles: UserRole) -> Callable[[Principal], Principal]:
    allowed = set(allowed_roles)

    def _dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{principal.role.value}' does not have permission for this action",
            )
        return principal

    return _dependency
