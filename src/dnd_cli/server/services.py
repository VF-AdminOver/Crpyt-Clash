from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dnd_cli.server.models import Account, Character, RefreshToken
from dnd_cli.server.security import SecurityManager, TokenBundle

VALID_ARCHETYPES = {"Fighter", "Rogue", "Cleric", "Mage"}


class ServiceError(ValueError):
    pass


async def register_account(session: AsyncSession, security: SecurityManager, username: str, password: str) -> Account:
    username_normalized = username.strip()
    if not username_normalized:
        raise ServiceError("Username cannot be empty.")
    existing = await session.scalar(select(Account).where(func.lower(Account.username) == username_normalized.lower()))
    if existing:
        raise ServiceError("Username already exists.")
    account = Account(
        username=username_normalized,
        password_hash=security.hash_password(password),
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


async def authenticate_account(
    session: AsyncSession, security: SecurityManager, username: str, password: str
) -> tuple[Account, TokenBundle]:
    account = await session.scalar(select(Account).where(func.lower(Account.username) == username.strip().lower()))
    if not account or not security.verify_password(password, account.password_hash):
        raise ServiceError("Invalid credentials.")
    tokens = security.mint_tokens(str(account.id))
    refresh_hash = security.hash_refresh_token(tokens.refresh_token)
    session.add(
        RefreshToken(
            account_id=account.id,
            token_hash=refresh_hash,
            expires_at=tokens.refresh_expires_at.replace(tzinfo=None),
        )
    )
    account.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await session.commit()
    return account, tokens


async def rotate_refresh_token(session: AsyncSession, security: SecurityManager, refresh_token: str) -> tuple[Account, TokenBundle]:
    token_hash = security.hash_refresh_token(refresh_token)
    row = await session.scalar(
        select(RefreshToken).where(
            and_(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
            )
        )
    )
    if not row or row.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise ServiceError("Refresh token is invalid or expired.")
    account = await session.get(Account, row.account_id)
    if not account:
        raise ServiceError("Account not found.")
    row.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    tokens = security.mint_tokens(str(account.id))
    session.add(
        RefreshToken(
            account_id=account.id,
            token_hash=security.hash_refresh_token(tokens.refresh_token),
            expires_at=tokens.refresh_expires_at.replace(tzinfo=None),
        )
    )
    await session.commit()
    return account, tokens


async def revoke_refresh_token(session: AsyncSession, security: SecurityManager, refresh_token: str) -> None:
    token_hash = security.hash_refresh_token(refresh_token)
    row = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if row and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()


async def list_characters(session: AsyncSession, account_id: uuid.UUID) -> list[Character]:
    rows = await session.scalars(
        select(Character)
        .where(Character.account_id == account_id)
        .order_by(Character.slot_index.asc(), Character.updated_at.desc())
    )
    return list(rows)


def _default_stats(archetype: str) -> dict:
    if archetype == "Fighter":
        return {"str": 15, "dex": 11, "con": 14, "int": 9, "wis": 10, "cha": 10}
    if archetype == "Rogue":
        return {"str": 10, "dex": 15, "con": 11, "int": 12, "wis": 10, "cha": 10}
    if archetype == "Cleric":
        return {"str": 11, "dex": 10, "con": 12, "int": 10, "wis": 15, "cha": 10}
    return {"str": 9, "dex": 12, "con": 10, "int": 15, "wis": 11, "cha": 10}


async def create_character(session: AsyncSession, account_id: uuid.UUID, name: str, archetype: str) -> Character:
    normalized_arch = archetype.strip().title()
    if normalized_arch not in VALID_ARCHETYPES:
        raise ServiceError(f"Invalid archetype. Choose one of: {', '.join(sorted(VALID_ARCHETYPES))}.")
    existing = await list_characters(session, account_id)
    used_slots = {character.slot_index for character in existing}
    slot_index = next((slot for slot in range(3) if slot not in used_slots), None)
    if slot_index is None:
        raise ServiceError("Character limit reached (max 3).")
    character = Character(
        account_id=account_id,
        slot_index=slot_index,
        name=name.strip(),
        archetype=normalized_arch,
        level=1,
        xp=0,
        gold=0,
        stats_jsonb=_default_stats(normalized_arch),
        inventory_jsonb={"healing_potion": 2},
        equipment_jsonb={},
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(character)
    await session.commit()
    await session.refresh(character)
    return character
