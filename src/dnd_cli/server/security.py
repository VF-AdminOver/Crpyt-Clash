from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


@dataclass(frozen=True)
class TokenBundle:
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime


class SecurityManager:
    def __init__(self, secret: str, access_token_minutes: int, refresh_token_days: int) -> None:
        self.secret = secret
        self.access_token_minutes = access_token_minutes
        self.refresh_token_days = refresh_token_days
        self.password_hasher = PasswordHasher()

    def hash_password(self, password: str) -> str:
        return self.password_hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            return self.password_hasher.verify(password_hash, password)
        except VerifyMismatchError:
            return False

    def mint_tokens(self, account_id: str) -> TokenBundle:
        now = datetime.now(timezone.utc)
        access_exp = now + timedelta(minutes=self.access_token_minutes)
        refresh_exp = now + timedelta(days=self.refresh_token_days)
        access_payload = {"sub": account_id, "typ": "access", "exp": int(access_exp.timestamp())}
        refresh_token = secrets.token_urlsafe(40)
        access_token = jwt.encode(access_payload, self.secret, algorithm="HS256")
        return TokenBundle(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=access_exp,
            refresh_expires_at=refresh_exp,
        )

    def decode_access_token(self, token: str) -> dict:
        payload = jwt.decode(token, self.secret, algorithms=["HS256"])
        if payload.get("typ") != "access":
            raise jwt.InvalidTokenError("Invalid token type")
        return payload

    @staticmethod
    def hash_refresh_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
