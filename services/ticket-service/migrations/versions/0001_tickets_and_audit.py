"""tickets + append-only ticket_audit

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# psycopg3 (extended query protocol) rejects multiple commands in one execute.
PG_GUARD_FN = """
CREATE OR REPLACE FUNCTION ticket_audit_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'ticket_audit is append-only';
END;
$$ LANGUAGE plpgsql
"""
PG_GUARD_TRG = """
CREATE TRIGGER ticket_audit_no_update BEFORE UPDATE OR DELETE ON ticket_audit
  FOR EACH ROW EXECUTE FUNCTION ticket_audit_append_only()
"""


def upgrade() -> None:
    op.create_table(
        "tickets",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("site_id", sa.String(32), index=True),
        sa.Column("incident_id", sa.String(32), index=True),
        sa.Column("fault_type", sa.String(40)),
        sa.Column("runbook_ids", sa.JSON, nullable=False),
        sa.Column("source_ids", sa.JSON, nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_via", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.String(64)),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decision_note", sa.Text),
        sa.Column("version", sa.Integer, nullable=False),
    )
    op.create_table(
        "ticket_audit",
        sa.Column("seq", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ticket_id", sa.String(16), nullable=False, index=True),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("from_status", sa.String(16)),
        sa.Column("to_status", sa.String(16), nullable=False),
        sa.Column("detail", sa.JSON, nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False, unique=True),
    )
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(PG_GUARD_FN)
        op.execute(PG_GUARD_TRG)
    elif dialect == "sqlite":
        for ev in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER ticket_audit_no_{ev.lower()} BEFORE {ev} ON ticket_audit "
                "BEGIN SELECT RAISE(ABORT, 'ticket_audit is append-only'); END"
            )


def downgrade() -> None:
    op.drop_table("ticket_audit")
    op.drop_table("tickets")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS ticket_audit_append_only()")
