from __future__ import annotations

import os
from dataclasses import dataclass


def _to_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class ServerConfig:
    database_url: str
    jwt_secret: str
    access_token_minutes: int
    refresh_token_days: int
    presence_limit: int
    reaction_limit_count: int
    reaction_limit_window_seconds: int
    reconnect_grace_seconds: int
    motd: str

    @classmethod
    def from_env(cls) -> "ServerConfig":
        return cls(
            database_url=os.getenv("CRYPTCLASH_DATABASE_URL", "sqlite+aiosqlite:///./cryptclash.db"),
            jwt_secret=os.getenv("CRYPTCLASH_JWT_SECRET", "change-me"),
            access_token_minutes=_to_int(os.getenv("CRYPTCLASH_ACCESS_TOKEN_MINUTES", "30"), 30),
            refresh_token_days=_to_int(os.getenv("CRYPTCLASH_REFRESH_TOKEN_DAYS", "14"), 14),
            presence_limit=_to_int(os.getenv("CRYPTCLASH_PRESENCE_LIMIT", "50"), 50),
            reaction_limit_count=_to_int(os.getenv("CRYPTCLASH_REACTION_LIMIT_COUNT", "4"), 4),
            reaction_limit_window_seconds=_to_int(os.getenv("CRYPTCLASH_REACTION_LIMIT_WINDOW_SECONDS", "10"), 10),
            reconnect_grace_seconds=_to_int(os.getenv("CRYPTCLASH_RECONNECT_GRACE_SECONDS", "60"), 60),
            motd=os.getenv("CRYPTCLASH_MOTD", "Welcome to Crypt Clash Online"),
        )
