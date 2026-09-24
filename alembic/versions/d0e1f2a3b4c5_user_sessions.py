"""Record login sessions so a single one can be revoked.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-23

The first incident tabletop (2026-09-22) found that containing one stolen
token meant deactivating the account or rotating the global signing key, and
that a token belonging to the operator's own account could not be contained at
all: the user endpoints refuse to deactivate your own account or the last
active super_admin (#368 phase C.3).

Tokens now carry a ``sid`` claim naming a row in this table, and every
authenticated request resolves the user through it, so setting ``revoked_at``
stops that session and no other.

Existing tokens carry no ``sid`` and are rejected from the deploy that applies
this, which costs one re-login and leaves no unrevocable token behind.

The table stores no token and no key material: ``sid`` is an opaque identifier,
useless without the signed token that carries it.
"""

import sqlalchemy as sa
from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None

_TABLE = "user_sessions"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sid", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column(
            "revoked_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("user_agent", sa.String(length=400), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
    )
    op.create_index(f"ix_{_TABLE}_sid", _TABLE, ["sid"], unique=True)
    op.create_index(f"ix_{_TABLE}_user_id", _TABLE, ["user_id"])
    op.create_index(f"ix_{_TABLE}_revoked_at", _TABLE, ["revoked_at"])


def downgrade() -> None:
    op.drop_index(f"ix_{_TABLE}_revoked_at", table_name=_TABLE)
    op.drop_index(f"ix_{_TABLE}_user_id", table_name=_TABLE)
    op.drop_index(f"ix_{_TABLE}_sid", table_name=_TABLE)
    op.drop_table(_TABLE)
