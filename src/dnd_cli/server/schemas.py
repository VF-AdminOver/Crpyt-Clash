from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ErrorPayload(BaseModel):
    v: int = 1
    type: str = "error"
    request_id: str | None = None
    code: str
    message: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_expires_at: datetime
    refresh_expires_at: datetime


class CharacterCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=30)
    archetype: str = Field(min_length=3, max_length=30)


class CharacterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slot_index: int
    name: str
    archetype: str
    level: int
    xp: int
    gold: int
    stats_jsonb: dict
    inventory_jsonb: dict
    equipment_jsonb: dict
    updated_at: datetime
