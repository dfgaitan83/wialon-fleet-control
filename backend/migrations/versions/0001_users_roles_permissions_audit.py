"""Tablas de usuarios, roles, permisos, refresh tokens y auditoría.

Revision ID: 0001
Revises:
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("description", sa.String(200), nullable=False, server_default=""),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(32), nullable=False, unique=True),
        sa.Column("label", sa.String(64), nullable=False),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "permission_id", sa.Integer, sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
        ),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("must_change_password", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("failed_login_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("locked_until", _TS, nullable=True),
        sa.Column("created_at", _TS, nullable=False),
        sa.Column("updated_at", _TS, nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("family_id", sa.String(32), nullable=False),
        sa.Column("expires_at", _TS, nullable=False),
        sa.Column("revoked_at", _TS, nullable=True),
        sa.Column("created_at", _TS, nullable=False),
    )
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("occurred_at", _TS, nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("actor_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_email", sa.String(254), nullable=True),
        sa.Column("entity_type", sa.String(32), nullable=True),
        sa.Column("entity_id", sa.String(64), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("details", sa.JSON, nullable=True),
    )
    op.create_index("ix_audit_log_occurred_at", "audit_log", ["occurred_at"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    op.drop_table("role_permissions")
    op.drop_table("roles")
    op.drop_table("permissions")
