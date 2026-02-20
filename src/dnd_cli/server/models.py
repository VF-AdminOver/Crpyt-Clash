from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def _json_type():
    return JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    characters: Mapped[list["Character"]] = relationship(back_populates="account")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Character(Base):
    __tablename__ = "characters"
    __table_args__ = (UniqueConstraint("account_id", "slot_index", name="uq_characters_account_slot"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True)
    slot_index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    archetype: Mapped[str] = mapped_column(String(30), nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stats_jsonb: Mapped[dict] = mapped_column(_json_type(), default=dict, nullable=False)
    inventory_jsonb: Mapped[dict] = mapped_column(_json_type(), default=dict, nullable=False)
    equipment_jsonb: Mapped[dict] = mapped_column(_json_type(), default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    account: Mapped[Account] = relationship(back_populates="characters")


class Party(Base):
    __tablename__ = "parties"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    leader_character_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id"), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(30), default="forming", nullable=False)
    chat_mode: Mapped[str] = mapped_column(String(30), default="reactions_only", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class PartyMember(Base):
    __tablename__ = "party_members"
    __table_args__ = (UniqueConstraint("party_id", "character_id", name="uq_party_character"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    party_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=False, index=True)
    character_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id"), nullable=False, index=True)
    role: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ready: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class Instance(Base):
    __tablename__ = "instances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    party_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=False, index=True)
    seed: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    dungeon_type: Mapped[str] = mapped_column(String(40), default="standard", nullable=False)
    state: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
