"""initial online schema

Revision ID: 20260219_0001
Revises:
Create Date: 2026-02-19 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260219_0001"
down_revision = None
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("username", sa.String(length=40), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_accounts_username", "accounts", ["username"], unique=True)

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_refresh_tokens_account_id", "refresh_tokens", ["account_id"], unique=False)
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)

    op.create_table(
        "characters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("slot_index", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("archetype", sa.String(length=30), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("xp", sa.Integer(), nullable=False),
        sa.Column("gold", sa.Integer(), nullable=False),
        sa.Column("stats_jsonb", _json_type(), nullable=False),
        sa.Column("inventory_jsonb", _json_type(), nullable=False),
        sa.Column("equipment_jsonb", _json_type(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", "slot_index", name="uq_characters_account_slot"),
    )
    op.create_index("ix_characters_account_id", "characters", ["account_id"], unique=False)

    op.create_table(
        "parties",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("leader_character_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("chat_mode", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_parties_leader_character_id", "parties", ["leader_character_id"], unique=False)

    op.create_table(
        "party_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("party_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=True),
        sa.Column("ready", sa.Boolean(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("party_id", "character_id", name="uq_party_character"),
    )
    op.create_index("ix_party_members_party_id", "party_members", ["party_id"], unique=False)
    op.create_index("ix_party_members_character_id", "party_members", ["character_id"], unique=False)

    op.create_table(
        "instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("party_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("dungeon_type", sa.String(length=40), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_instances_party_id", "instances", ["party_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_instances_party_id", table_name="instances")
    op.drop_table("instances")
    op.drop_index("ix_party_members_character_id", table_name="party_members")
    op.drop_index("ix_party_members_party_id", table_name="party_members")
    op.drop_table("party_members")
    op.drop_index("ix_parties_leader_character_id", table_name="parties")
    op.drop_table("parties")
    op.drop_index("ix_characters_account_id", table_name="characters")
    op.drop_table("characters")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_account_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_accounts_username", table_name="accounts")
    op.drop_table("accounts")
